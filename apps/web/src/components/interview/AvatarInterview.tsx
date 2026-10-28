"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  createClient,
  TruGenEvent,
  type TruGenSession,
} from "@trugen/js-sdk";
import {
  Bot,
  CircleStop,
  Loader2,
  Mic,
  MicOff,
  SendHorizontal,
  Video,
  VideoOff,
} from "lucide-react";

import { useAuth } from "@/components/AuthProvider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  endInterview,
  getAvatarToken,
  type InterviewReportResponse,
} from "@/lib/api";
import { userFacingMessage } from "@/lib/errors";
import { cn } from "@/lib/utils";

/** One caption line. Speech arrives as a growing segment that is upserted by id until
 * it is final; typed answers arrive whole. */
interface Caption {
  id: string;
  role: "interviewer" | "you";
  text: string;
  final: boolean;
}

type Phase = "ready" | "connecting" | "live" | "ending" | "error";

/** The LiveKit room the TruGen SDK manages internally. Reached for two things the SDK
 * does not expose: captions tagged with *who* spoke (the SDK's own caption event drops
 * the speaker), and typed answers, which TruGen agents accept on LiveKit's standard
 * `lk.chat` text topic. Both were verified against a live agent. */
interface RoomLike {
  localParticipant: {
    identity: string;
    sendText: (text: string, options: { topic: string }) => Promise<unknown>;
  };
  on: (event: string, fn: (...args: never[]) => void) => unknown;
}

interface Segment {
  id: string;
  text: string;
  final: boolean;
}

function roomOf(session: TruGenSession): RoomLike | null {
  const transport = (session as unknown as { transport?: { room?: RoomLike } })
    .transport;
  return transport?.room ?? null;
}

function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

interface AvatarInterviewProps {
  sessionId: string;
  roleTitle?: string | null;
  topics: string[];
  onReport: (report: InterviewReportResponse) => void;
}

/** Live interview with a TruGen video avatar: the candidate's camera on one side, the
 * interviewer on the other, live captions underneath, and a text box for typed answers.
 *
 * Speech recognition and the interviewer's voice run inside TruGen's pipeline, so there
 * is no browser SpeechRecognition or speechSynthesis here. Scoring happens server-side on
 * `/end`, from TruGen's stored transcript, by the same report agent as the classic mode.
 */
export function AvatarInterview({
  sessionId,
  roleTitle,
  topics,
  onReport,
}: AvatarInterviewProps) {
  const { getToken } = useAuth();

  const [phase, setPhase] = useState<Phase>("ready");
  const [error, setError] = useState<string | null>(null);
  const [captions, setCaptions] = useState<Caption[]>([]);
  const [agentSpeaking, setAgentSpeaking] = useState(false);
  const [userSpeaking, setUserSpeaking] = useState(false);
  const [micMuted, setMicMuted] = useState(false);
  const [cameraOn, setCameraOn] = useState(false);
  const [typed, setTyped] = useState("");
  const [sending, setSending] = useState(false);
  const [elapsed, setElapsed] = useState(0);

  const sessionRef = useRef<TruGenSession | null>(null);
  const avatarVideoRef = useRef<HTMLVideoElement>(null);
  const selfVideoRef = useRef<HTMLVideoElement>(null);
  const cameraStreamRef = useRef<MediaStream | null>(null);
  const captionsEndRef = useRef<HTMLDivElement>(null);

  const upsertCaption = useCallback((caption: Caption) => {
    setCaptions((prev) => {
      const index = prev.findIndex((c) => c.id === caption.id);
      if (index === -1) return [...prev, caption];
      const next = prev.slice();
      next[index] = caption;
      return next;
    });
  }, []);

  // Keep the newest caption in view.
  useEffect(() => {
    captionsEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [captions]);

  // Interview clock, only while connected.
  useEffect(() => {
    if (phase !== "live") return;
    const timer = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(timer);
  }, [phase]);

  const startCamera = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 1280, height: 720, facingMode: "user" },
        audio: false,
      });
      cameraStreamRef.current = stream;
      setCameraOn(true);
    } catch {
      // The interview still works without video: the avatar only needs the microphone.
      setCameraOn(false);
    }
  }, []);

  const stopCamera = useCallback(() => {
    cameraStreamRef.current?.getTracks().forEach((t) => t.stop());
    cameraStreamRef.current = null;
    setCameraOn(false);
  }, []);

  // The <video> mounts only once cameraOn flips, so attach the stream afterwards.
  useEffect(() => {
    if (cameraOn && selfVideoRef.current && cameraStreamRef.current) {
      selfVideoRef.current.srcObject = cameraStreamRef.current;
    }
  }, [cameraOn]);

  // Release every device and the TruGen connection on unmount. A session left open
  // keeps holding the plan's single concurrent-session slot.
  useEffect(() => {
    return () => {
      cameraStreamRef.current?.getTracks().forEach((t) => t.stop());
      void sessionRef.current?.disconnect();
      sessionRef.current = null;
    };
  }, []);

  async function connect() {
    setError(null);
    setPhase("connecting");
    try {
      const token = await getToken();
      if (!token) throw new Error("No session token");
      void startCamera();

      const minted = await getAvatarToken(token, sessionId);
      const session = await createClient({ token: minted.token });
      sessionRef.current = session;

      session.on(TruGenEvent.VIDEO_STREAM_STARTED, (track: { attach: (el: HTMLMediaElement) => void }) => {
        if (avatarVideoRef.current) track.attach(avatarVideoRef.current);
      });
      session.on(TruGenEvent.AGENT_SPEAKING_STARTED, () => setAgentSpeaking(true));
      session.on(TruGenEvent.AGENT_SPEAKING_ENDED, () => setAgentSpeaking(false));
      session.on(TruGenEvent.USER_SPEECH_STARTED, () => setUserSpeaking(true));
      session.on(TruGenEvent.USER_SPEECH_ENDED, () => setUserSpeaking(false));
      session.on(TruGenEvent.CONNECTION_ESTABLISHED, () => setPhase("live"));
      session.on(TruGenEvent.CONNECTION_CLOSED, () => {
        setAgentSpeaking(false);
        setUserSpeaking(false);
      });
      session.on(TruGenEvent.MIC_PERMISSION_DENIED, () =>
        setError(
          "Microphone access was blocked. You can still answer by typing below.",
        ),
      );

      // `connect()` builds the LiveKit room synchronously before its first await, so the
      // caption listener is attached before the interviewer's first word.
      const connecting = session.connect();
      const room = roomOf(session);
      room?.on(
        "transcriptionReceived",
        (segments: Segment[], participant?: { identity: string }) => {
          const isYou =
            participant?.identity === room.localParticipant.identity;
          for (const segment of segments) {
            const text = segment.text.trim();
            if (!text) continue;
            upsertCaption({
              id: segment.id,
              role: isYou ? "you" : "interviewer",
              text,
              final: segment.final,
            });
          }
        },
      );
      await connecting;
      setPhase("live");
    } catch (err) {
      setPhase("error");
      setError(userFacingMessage(err));
      void sessionRef.current?.disconnect();
      sessionRef.current = null;
    }
  }

  async function sendTyped(e: React.FormEvent) {
    e.preventDefault();
    const text = typed.trim();
    const session = sessionRef.current;
    if (!text || !session || sending) return;
    const room = roomOf(session);
    if (!room) {
      setError("Typing isn't available on this connection. Please answer by voice.");
      return;
    }
    setSending(true);
    try {
      await room.localParticipant.sendText(text, { topic: "lk.chat" });
      upsertCaption({ id: `typed-${Date.now()}`, role: "you", text, final: true });
      setTyped("");
    } catch (err) {
      setError(userFacingMessage(err));
    } finally {
      setSending(false);
    }
  }

  function toggleMic() {
    const session = sessionRef.current;
    if (!session) return;
    const state = micMuted ? session.unmuteInputAudio() : session.muteInputAudio();
    setMicMuted(state.isMuted);
  }

  async function finish() {
    setPhase("ending");
    setError(null);
    try {
      await sessionRef.current?.disconnect();
      sessionRef.current = null;
      stopCamera();
      const token = await getToken();
      if (!token) throw new Error("No session token");
      const report = await endInterview(token, sessionId);
      onReport(report);
    } catch (err) {
      // Most likely nothing was answered yet. The session stays open server-side, so
      // the candidate can reconnect and carry on.
      setError(userFacingMessage(err));
      setPhase("ready");
    }
  }

  const live = phase === "live";
  const busy = phase === "connecting" || phase === "ending";

  return (
    <div className="space-y-4">
      {/* Session bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-card px-4 py-3 shadow-flat">
        <div className="flex min-w-0 items-center gap-3">
          <span
            aria-hidden
            className={cn(
              "size-2.5 shrink-0 rounded-full",
              live ? "animate-pulse bg-destructive" : "bg-muted-foreground/40",
            )}
          />
          <div className="min-w-0">
            <p className="truncate text-body font-medium text-foreground">
              {roleTitle || "Practice interview"}
            </p>
            <p className="text-meta text-muted-foreground">
              {live
                ? `Live · ${formatElapsed(elapsed)}`
                : phase === "connecting"
                  ? "Connecting to your interviewer"
                  : phase === "ending"
                    ? "Scoring your answers"
                    : "Not started"}
              {topics.length > 0 ? ` · ${topics.length} topics` : ""}
            </p>
          </div>
        </div>
        <Badge variant="secondary" className="gap-1.5">
          <Bot aria-hidden className="size-3.5" />
          AI video interviewer
        </Badge>
      </div>

      {/* Stage: you on one side, the interviewer on the other */}
      <div className="grid gap-4 md:grid-cols-2">
        <VideoTile
          label="You"
          speaking={userSpeaking && !micMuted}
          status={micMuted ? "Muted" : userSpeaking ? "Speaking" : undefined}
        >
          {cameraOn ? (
            <video
              ref={selfVideoRef}
              autoPlay
              playsInline
              muted
              className="size-full -scale-x-100 object-cover"
            />
          ) : (
            <TilePlaceholder icon={VideoOff} text="Camera off" />
          )}
        </VideoTile>

        <VideoTile
          label="Interviewer"
          speaking={agentSpeaking}
          status={live ? (agentSpeaking ? "Speaking" : "Listening") : undefined}
        >
          <video
            ref={avatarVideoRef}
            autoPlay
            playsInline
            className={cn("size-full object-cover", !live && "hidden")}
          />
          {!live && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 p-6 text-center">
              {busy ? (
                <>
                  <Loader2 aria-hidden className="size-8 animate-spin text-primary" />
                  <p className="text-body text-muted-foreground">
                    {phase === "ending"
                      ? "Generating your interview report"
                      : "Your interviewer is joining"}
                  </p>
                </>
              ) : (
                <>
                  <span className="flex size-14 items-center justify-center rounded-full bg-primary/10">
                    <Bot aria-hidden className="size-7 text-primary" />
                  </span>
                  <div className="space-y-1">
                    <p className="text-section font-semibold text-foreground">
                      Ready when you are
                    </p>
                    <p className="text-body text-muted-foreground">
                      Answer out loud, or type if you prefer. Say hello to begin.
                    </p>
                  </div>
                  <Button size="lg" onClick={connect}>
                    <Video aria-hidden className="size-4" />
                    {phase === "error" || captions.length > 0
                      ? "Reconnect"
                      : "Start interview"}
                  </Button>
                </>
              )}
            </div>
          )}
        </VideoTile>
      </div>

      {error && (
        <p role="alert" className="rounded-md bg-destructive/10 px-3 py-2 text-body text-destructive">
          {error}
        </p>
      )}

      {/* Captions + typed answers */}
      <div className="rounded-lg bg-card shadow-flat">
        <div className="flex items-center justify-between px-4 pt-3">
          <h2 className="text-meta font-medium text-muted-foreground">
            Live transcript
          </h2>
          {topics.length > 0 && (
            <p className="hidden truncate text-meta text-muted-foreground sm:block">
              Topics: {topics.join(", ")}
            </p>
          )}
        </div>
        <div
          className="h-56 space-y-2 overflow-y-auto px-4 py-3"
          aria-live="polite"
        >
          {captions.length === 0 ? (
            <p className="text-body text-muted-foreground">
              What you and the interviewer say will appear here.
            </p>
          ) : (
            captions.map((c) => (
              <div
                key={c.id}
                className={cn(
                  "flex",
                  c.role === "you" ? "justify-end" : "justify-start",
                )}
              >
                <p
                  className={cn(
                    "max-w-[85%] rounded-lg px-3 py-2 text-body",
                    c.role === "you"
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted text-foreground",
                    !c.final && "opacity-70",
                  )}
                >
                  <span className="mb-0.5 block text-meta font-medium opacity-75">
                    {c.role === "you" ? "You" : "Interviewer"}
                  </span>
                  {c.text}
                </p>
              </div>
            ))
          )}
          <div ref={captionsEndRef} />
        </div>

        <form
          onSubmit={sendTyped}
          className="flex flex-wrap items-center gap-2 border-t border-border p-3"
        >
          <Button
            type="button"
            variant={micMuted ? "destructive" : "secondary"}
            size="sm"
            onClick={toggleMic}
            disabled={!live}
            aria-pressed={micMuted}
            aria-label={micMuted ? "Unmute microphone" : "Mute microphone"}
          >
            {micMuted ? (
              <MicOff aria-hidden className="size-4" />
            ) : (
              <Mic aria-hidden className="size-4" />
            )}
            {micMuted ? "Muted" : "Mic on"}
          </Button>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => (cameraOn ? stopCamera() : void startCamera())}
            aria-pressed={cameraOn}
            aria-label={cameraOn ? "Turn camera off" : "Turn camera on"}
          >
            {cameraOn ? (
              <Video aria-hidden className="size-4" />
            ) : (
              <VideoOff aria-hidden className="size-4" />
            )}
            {cameraOn ? "Camera on" : "Camera off"}
          </Button>
          <Input
            className="min-w-40 flex-1"
            aria-label="Type your answer"
            placeholder={live ? "Type an answer instead of speaking" : "Start the interview to answer"}
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            disabled={!live}
          />
          <Button
            type="submit"
            size="sm"
            disabled={!live || sending || !typed.trim()}
            aria-label="Send typed answer"
          >
            <SendHorizontal aria-hidden className="size-4" />
            Send
          </Button>
          <Button
            type="button"
            variant="destructive"
            size="sm"
            onClick={finish}
            disabled={phase !== "live"}
          >
            <CircleStop aria-hidden className="size-4" />
            End interview
          </Button>
        </form>
      </div>

      <p className="text-meta text-muted-foreground">
        Your camera stays on your device and is never sent or recorded. Only the
        conversation transcript is kept, to generate your report.
      </p>
    </div>
  );
}

function VideoTile({
  label,
  speaking,
  status,
  children,
}: {
  label: string;
  speaking: boolean;
  status?: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className={cn(
        "relative aspect-video overflow-hidden rounded-xl bg-muted shadow-raised ring-2 transition-shadow duration-(--animate-duration-base)",
        speaking ? "ring-primary" : "ring-transparent",
      )}
    >
      {children}
      <div className="pointer-events-none absolute inset-x-0 bottom-0 flex items-center justify-between gap-2 p-3">
        <span className="rounded-md bg-background/85 px-2 py-1 text-meta font-medium text-foreground backdrop-blur-sm">
          {label}
        </span>
        {status && (
          <span className="flex items-center gap-1.5 rounded-md bg-background/85 px-2 py-1 text-meta text-foreground backdrop-blur-sm">
            {speaking && (
              <span aria-hidden className="size-1.5 animate-pulse rounded-full bg-primary" />
            )}
            {status}
          </span>
        )}
      </div>
    </div>
  );
}

function TilePlaceholder({
  icon: Icon,
  text,
}: {
  icon: React.ComponentType<{ className?: string }>;
  text: string;
}) {
  return (
    <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-muted-foreground">
      <Icon aria-hidden className="size-8" />
      <p className="text-body">{text}</p>
    </div>
  );
}
