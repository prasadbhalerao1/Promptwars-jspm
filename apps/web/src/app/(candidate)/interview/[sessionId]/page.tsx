"use client";

import { Page, PageHeader } from "@/components/common/PageHeader";

import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { useParams, useRouter } from "next/navigation";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Mic, MicOff, Video, VideoOff } from "lucide-react";
import {
  endInterview,
  getInterviewSession,
  interviewTurn,
  startInterview,
  type InterviewMode,
  type InterviewReportResponse,
} from "@/lib/api";
import { Input } from "@/components/ui/input";
import { AvatarInterview } from "@/components/interview/AvatarInterview";

interface ChatMessage {
  role: "ai" | "user";
  text: string;
}

// Web Speech API isn't in the standard TS lib — feature-detected at runtime, typed as
// unknown here rather than pulling in a whole ambient-types package for one page.
type SpeechRecognitionLike = {
  start: () => void;
  stop: () => void;
  onresult: ((e: unknown) => void) | null;
  onend: (() => void) | null;
  lang: string;
  interimResults: boolean;
};

export default function CandidateInterviewPage() {
  const params = useParams<{ sessionId: string }>();
  const router = useRouter();
  const { getToken } = useAuth();

  const initialSessionId = params.sessionId !== "new" ? params.sessionId : null;
  // A session exists and the chat UI should render.
  const [sessionStarted, setSessionStarted] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(initialSessionId);
  const [hydrating, setHydrating] = useState(initialSessionId !== null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState("");
  const [listening, setListening] = useState(false);
  const [interimTranscript, setInterimTranscript] = useState("");
  const [speechConfidence, setSpeechConfidence] = useState<number | null>(null);
  const [status, setStatus] = useState<"in_progress" | "completed" | null>(
    null,
  );
  const [report, setReport] = useState<InterviewReportResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [awaitingResponse, setAwaitingResponse] = useState(false);
  const [cameraActive, setCameraActive] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [mode, setMode] = useState<InterviewMode>("classic");
  const [roleTitle, setRoleTitle] = useState<string | null>(null);
  const [topics, setTopics] = useState<string[]>([]);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  // Current interim transcript, readable from the `onend` handler (see toggleSpeech).
  const interimTranscriptRef = useRef("");
  // Index of the last message read aloud, so re-renders don't stack duplicate speech.
  const lastSpokenIndexRef = useRef(-1);
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const handleStart = useCallback(async () => {
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("No session token");
      const result = await startInterview(token);
      setSessionId(result.session_id);
      setStatus(result.status);
      if (result.question) setMessages([{ role: "ai", text: result.question }]);
      setSessionStarted(true);
      router.replace(`/interview/${result.session_id}`);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to start interview",
      );
    }
  }, [getToken, router]);

  // /interview/new has nothing to confirm before starting, so the session is created on
  // arrival — the camera/mic check happens earlier, in the lobby on /interviews.
  const startRequested = useRef(false);
  useEffect(() => {
    if (initialSessionId || startRequested.current) return;
    startRequested.current = true;
    void handleStart();
  }, [initialSessionId, handleStart]);

  useEffect(() => {
    // Landing directly on /interview/{sessionId} (fresh navigation, reload, or a shared
    // link) — the first question only ever comes back in the POST /interview-sessions
    // response, so without this the chat renders empty until the candidate types
    // something. Hydrate the transcript so far and resume from there.
    if (!initialSessionId) return;
    let cancelled = false;
    (async () => {
      try {
        const token = await getToken();
        if (!token) throw new Error("No session token");
        const session = await getInterviewSession(token, initialSessionId);
        if (cancelled) return;
        setMessages(
          session.transcript.map((t) => ({
            role: t.role === "agent" ? "ai" : "user",
            text: t.text,
          })),
        );
        setStatus(session.status);
        setMode(session.mode ?? "classic");
        setRoleTitle(session.role_title ?? null);
        setTopics(session.topics ?? []);
        setSessionStarted(true);
      } catch (err) {
        if (!cancelled)
          setError(
            err instanceof Error
              ? err.message
              : "Failed to load interview session",
          );
      } finally {
        if (!cancelled) setHydrating(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialSessionId]);

  async function handleSend() {
    if (!inputText.trim() || !sessionId || awaitingResponse) return;
    const userMsg = inputText;
    setInputText("");
    setMessages((prev) => [...prev, { role: "user", text: userMsg }]);
    setError(null);
    setAwaitingResponse(true);
    try {
      const token = await getToken();
      if (!token) throw new Error("No session token");
      const result = await interviewTurn(token, sessionId, userMsg);
      setStatus(result.status);
      if (result.question) {
        setMessages((prev) => [
          ...prev,
          { role: "ai", text: result.question as string },
        ]);
      } else if (result.status === "completed") {
        setMessages((prev) => [
          ...prev,
          {
            role: "ai",
            text: "That covers everything - generating your report now…",
          },
        ]);
        const finalReport = await endInterview(token, sessionId);
        setReport(finalReport);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send answer");
    } finally {
      setAwaitingResponse(false);
    }
  }

  function toggleSpeech() {
    if (listening) {
      recognitionRef.current?.stop();
      setListening(false);
      setInterimTranscript("");
      interimTranscriptRef.current = "";
      setSpeechConfidence(null);
      return;
    }
    const SpeechRecognitionCtor = (
      window as unknown as {
        webkitSpeechRecognition?: new () => SpeechRecognitionLike;
      }
    ).webkitSpeechRecognition;
    if (!SpeechRecognitionCtor) {
      setError(
        "Speech recognition isn't supported in this browser - use the text box instead.",
      );
      return;
    }
    const recognition = new SpeechRecognitionCtor();
    recognition.lang = "en-US";
    recognition.interimResults = true;
    recognition.onresult = (e: unknown) => {
      const event = e as {
        results: {
          transcript: string;
          isFinal: boolean;
          confidence?: number;
        }[][];
      };
      let interim = "";
      let final = "";
      let confidence = 0;

      for (let i = 0; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i][0].isFinal) {
          final += transcript;
          confidence = Math.max(
            confidence,
            event.results[i][0].confidence || 0,
          );
        } else {
          interim += transcript;
        }
      }

      if (final) {
        setInputText((prev) => prev + final);
        setSpeechConfidence(
          confidence > 0 ? Math.round(confidence * 100) : null,
        );
      }
      setInterimTranscript(interim);
      // Mirrored into a ref so `onend` — created once and therefore holding a stale
      // closure over state — can read the current value.
      interimTranscriptRef.current = interim;
    };
    recognition.onend = () => {
      setListening(false);
      // Read the ref, not the `interimTranscript` state. This handler is created once,
      // when recognition starts, so it closes over whatever the state was at that
      // moment — always "" — and the last partial phrase was silently dropped every
      // time speech ended on a non-final result.
      const pending = interimTranscriptRef.current.trim();
      if (pending) {
        setInputText(
          (prev) => prev + (prev.endsWith(" ") ? "" : " ") + pending,
        );
      }
      setInterimTranscript("");
      interimTranscriptRef.current = "";
    };
    recognitionRef.current = recognition;
    recognition.start();
    setListening(true);
    setSpeechConfidence(null);
  }

  async function toggleCamera() {
    if (cameraActive) {
      // Stop camera
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      setCameraActive(false);
      setCameraError(null);
      return;
    }

    // Start camera
    setCameraError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: true,
        audio: false,
      });
      streamRef.current = stream;
      setCameraActive(true);
    } catch (err) {
      setCameraError(
        err instanceof Error ? err.message : "Failed to access camera",
      );
    }
  }

  useEffect(() => {
    // The <video> element only mounts once cameraActive is true, so attach the
    // already-acquired stream here rather than in toggleCamera (videoRef.current
    // is still null at the moment getUserMedia resolves).
    if (cameraActive && videoRef.current && streamRef.current) {
      videoRef.current.srcObject = streamRef.current;
    }
  }, [cameraActive]);

  useEffect(() => {
    return () => {
      // Every device resource this page acquires must be released here. Stopping the
      // camera tracks alone left two things running after the user navigated away:
      // speech recognition (the browser keeps the microphone open, and the OS recording
      // indicator stays lit on a page that no longer exists) and queued TTS (the
      // unmounted page keeps talking).
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      recognitionRef.current?.stop();
      recognitionRef.current = null;
      if ("speechSynthesis" in window) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  useEffect(() => {
    // "SpeechSynthesis" TTS: speak the latest AI question aloud, browser-native, no
    // audio persisted anywhere (doc 03 §3).
    //
    // Guarded by the index of the last message actually spoken. This effect depends on
    // the whole `messages` array, so it re-ran on every append — including the
    // candidate's own answers — and `speak()` *queues* rather than replaces, so each
    // re-run stacked another reading of the same question on top of the one still
    // playing. Tracking the index means each AI message is spoken exactly once.
    const lastIndex = messages.length - 1;
    const last = messages[lastIndex];
    if (!last || last.role !== "ai") return;
    if (lastIndex === lastSpokenIndexRef.current) return;
    if (!("speechSynthesis" in window)) return;

    lastSpokenIndexRef.current = lastIndex;
    // Cancel anything still playing before starting the new question: a follow-up can
    // arrive while the previous one is mid-sentence.
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(new SpeechSynthesisUtterance(last.text));
  }, [messages]);

  if (hydrating) {
    return (
      <div className="max-w-lg mx-auto p-8 text-sm text-muted-foreground">
        Loading interview…
      </div>
    );
  }

  // Landing on /interview/new with no session yet: the effect above creates one on
  // mount, so this is purely the window before that request resolves.
  if (!sessionStarted && !sessionId) {
    return (
      <div className="max-w-lg mx-auto p-8">
        <Card>
          <CardContent className="space-y-4 pt-6">
            {error ? (
              <>
                <p className="text-sm text-destructive">{error}</p>
                <Button onClick={handleStart} className="w-full">
                  Try again
                </Button>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">
                Starting your interview…
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    );
  }

  if (report) {
    return (
      <div className="max-w-2xl mx-auto p-8 space-y-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-base font-semibold">
              Interview Complete
            </CardTitle>
            <CardDescription>
              Your report has been generated and shared with the recruiter.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-muted-foreground">
            <p>
              Technical Rating: {report.technical_rating?.toFixed(0) ?? "Not recorded"}/100
            </p>
            <p>
              Communication Rating:{" "}
              {report.communication_rating?.toFixed(0) ?? "Not recorded"}/100
            </p>
            <p>{report.hiring_recommendation}</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (mode === "avatar" && sessionId) {
    return (
      <Page>
        <PageHeader
          title="Interview"
          description="A live interview with an AI video interviewer. Speak your answers, or type them."
        />
        {status === "completed" ? (
          <p className="text-body text-muted-foreground">
            This interview has finished. Your report has been shared with the recruiter.
          </p>
        ) : (
          <AvatarInterview
            sessionId={sessionId}
            roleTitle={roleTitle}
            topics={topics}
            onReport={setReport}
          />
        )}
      </Page>
    );
  }

  return (
    <Page>
      <PageHeader
        title="Interview"
        description={
          status === "completed"
            ? "Wrapping up - your report will be ready shortly."
            : "Speak or type your answers."
        }
      />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="md:col-span-2 flex flex-col h-[500px]">
          <CardHeader>
            <CardTitle className="text-base font-semibold">
              Active Session
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col flex-1 space-y-4 overflow-hidden">
            <div className="flex-1 overflow-y-auto space-y-3 p-4 bg-card rounded-md border">
              {messages.map((m, i) => (
                <div
                  key={i}
                  className={`flex ${m.role === "ai" ? "justify-start" : "justify-end"}`}
                >
                  <div
                    className={`max-w-[80%] p-3 rounded-lg text-sm ${m.role === "ai" ? "bg-card text-foreground shadow-flat" : "bg-primary text-primary-foreground"}`}
                  >
                    <p className="font-semibold text-xs mb-1 opacity-70">
                      {m.role === "ai" ? "AI Interviewer" : "You"}
                    </p>
                    <p>{m.text}</p>
                  </div>
                </div>
              ))}
              {awaitingResponse && (
                <div className="flex justify-start" aria-live="polite">
                  <div className="max-w-[80%] p-3 rounded-lg text-sm bg-card text-foreground shadow-flat">
                    <p className="font-semibold text-xs mb-1 opacity-70">
                      AI Interviewer
                    </p>
                    <span className="sr-only">
                      The interviewer is preparing a response.
                    </span>
                    <p aria-hidden className="flex gap-1 items-center opacity-60">
                      <span className="inline-block h-1.5 w-1.5 rounded-full bg-current animate-bounce [animation-delay:-0.3s]" />
                      <span className="inline-block h-1.5 w-1.5 rounded-full bg-current animate-bounce [animation-delay:-0.15s]" />
                      <span className="inline-block h-1.5 w-1.5 rounded-full bg-current animate-bounce" />
                    </p>
                  </div>
                </div>
              )}
              {error && <p className="text-sm text-destructive">{error}</p>}
            </div>

            <div className="flex flex-col gap-2">
              <div className="flex gap-2">
                <Button
                  onClick={toggleSpeech}
                  variant={listening ? "destructive" : "secondary"}
                  size="sm"
                  disabled={awaitingResponse}
                  aria-pressed={listening}
                  aria-label={
                    listening ? "Stop dictation" : "Answer by voice"
                  }
                >
                  {listening ? (
                    <MicOff aria-hidden className="size-4" />
                  ) : (
                    <Mic aria-hidden className="size-4" />
                  )}
                  {listening ? "Listening" : "Speak"}
                </Button>
                <Button
                  onClick={toggleCamera}
                  variant={cameraActive ? "destructive" : "secondary"}
                  size="sm"
                  aria-pressed={cameraActive}
                  aria-label={
                    cameraActive ? "Turn camera off" : "Turn camera on"
                  }
                >
                  {cameraActive ? (
                    <VideoOff aria-hidden className="size-4" />
                  ) : (
                    <Video aria-hidden className="size-4" />
                  )}
                  {cameraActive ? "Camera on" : "Camera off"}
                </Button>
                <Input
                  className="flex-1"
                  aria-label="Your response"
                  placeholder={
                    awaitingResponse
                      ? "Waiting for the interviewer…"
                      : "Type your response..."
                  }
                  value={
                    inputText +
                    (interimTranscript ? ` ${interimTranscript}` : "")
                  }
                  onChange={(e) => setInputText(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleSend()}
                  disabled={awaitingResponse}
                />
                <Button
                  onClick={handleSend}
                  disabled={awaitingResponse || !inputText.trim()}
                >
                  {awaitingResponse ? "Thinking…" : "Send"}
                </Button>
              </div>
              {interimTranscript && (
                <p className="text-xs text-muted-foreground italic opacity-60">
                  {interimTranscript}
                </p>
              )}
              {speechConfidence !== null && (
                <p className="text-xs text-muted-foreground">
                  Confidence: {speechConfidence}%
                </p>
              )}
              {cameraError && (
                <p className="text-xs text-destructive">{cameraError}</p>
              )}
            </div>
          </CardContent>
        </Card>

        <div className="space-y-6">
          {cameraActive && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base font-semibold">
                  Camera
                </CardTitle>
              </CardHeader>
              <CardContent>
                <video
                  ref={videoRef}
                  autoPlay
                  playsInline
                  muted
                  className="w-full rounded-md border bg-black aspect-video object-cover"
                />
                <p className="text-xs text-muted-foreground mt-2">
                  Live video (not recorded or stored)
                </p>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle className="text-base font-semibold">
                Instructions
              </CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground space-y-2">
              <p>
                Speak or type your answer, then press Send. The interviewer
                adapts follow-up questions based on your answers.
              </p>
              <p className="text-xs pt-2 border-t">
                Optional: turn on your camera to practice on video. No
                recording - it&apos;s live only.
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </Page>
  );
}
