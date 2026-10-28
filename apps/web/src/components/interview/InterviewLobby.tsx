"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowLeft, Loader2, Mic, MicOff, Video, VideoOff } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

interface InterviewLobbyProps {
  topics: string[];
  title: string;
  /** Shown above the topic list — the role the interview is for. */
  roleTitle?: string;
  onJoin: () => void;
  onBack: () => void;
  joining: boolean;
}

type PermissionState =
  "prompt" | "granted" | "denied" | "no-device" | "unsupported";

/** Pre-interview device check, Google-Meet style: camera/mic preview on one side, the
 * topic outline on the other.
 *
 * This replaces a bare topic list whose "Start Interview" button dropped the candidate
 * straight into a live session — the first time they discovered a broken camera or a
 * muted mic was mid-answer.
 *
 * Three resources are acquired here and **all three** must be released on unmount: the
 * media tracks, the animation frame driving the level meter, and the AudioContext.
 * Leaving any one running keeps the OS recording indicator lit on a page the user has
 * already left.
 */
export function InterviewLobby({
  topics,
  title,
  roleTitle,
  onJoin,
  onBack,
  joining,
}: InterviewLobbyProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const rafRef = useRef<number | null>(null);

  const [permission, setPermission] = useState<PermissionState>("prompt");
  const [errorDetail, setErrorDetail] = useState<string | null>(null);
  const [cameraOn, setCameraOn] = useState(true);
  const [micOn, setMicOn] = useState(true);
  const [micLevel, setMicLevel] = useState(0);

  /** Stops everything this component started. Safe to call more than once. */
  const releaseDevices = useCallback(() => {
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    // close() returns a promise; a failure here is not actionable and must not surface
    // as an unhandled rejection during teardown.
    audioContextRef.current?.close().catch(() => undefined);
    audioContextRef.current = null;
  }, []);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      if (
        typeof navigator === "undefined" ||
        !navigator.mediaDevices?.getUserMedia
      ) {
        setPermission("unsupported");
        return;
      }

      try {
        // Audio as well as video, unlike the interview page's camera-only toggle — the
        // whole point of a lobby is to catch a dead mic before the interview starts.
        const stream = await navigator.mediaDevices.getUserMedia({
          video: true,
          audio: true,
        });
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }

        streamRef.current = stream;
        setPermission("granted");

        const AudioCtor =
          window.AudioContext ??
          (window as unknown as { webkitAudioContext?: typeof AudioContext })
            .webkitAudioContext;
        if (!AudioCtor) return;

        const context = new AudioCtor();
        audioContextRef.current = context;
        const analyser = context.createAnalyser();
        analyser.fftSize = 256;
        context.createMediaStreamSource(stream).connect(analyser);

        const buffer = new Uint8Array(analyser.frequencyBinCount);
        const tick = () => {
          analyser.getByteTimeDomainData(buffer);
          // Peak deviation from the 128 midpoint, normalized to 0-1. Peak rather than
          // RMS so a short word still visibly moves the meter.
          let peak = 0;
          for (const sample of buffer) {
            peak = Math.max(peak, Math.abs(sample - 128));
          }
          setMicLevel(Math.min(1, peak / 96));
          rafRef.current = requestAnimationFrame(tick);
        };
        rafRef.current = requestAnimationFrame(tick);
      } catch (err) {
        if (cancelled) return;
        const name = err instanceof Error ? err.name : "";
        // Distinguish "you said no" from "there is nothing to use" — the fixes differ.
        if (name === "NotFoundError" || name === "DevicesNotFoundError") {
          setPermission("no-device");
        } else if (
          name === "NotAllowedError" ||
          name === "PermissionDeniedError"
        ) {
          setPermission("denied");
        } else {
          setPermission("denied");
          setErrorDetail(err instanceof Error ? err.message : String(err));
        }
      }
    })();

    return () => {
      cancelled = true;
      releaseDevices();
    };
  }, [releaseDevices]);

  // Attaching in a separate effect, not where the stream is acquired: <video> is only
  // in the tree once permission resolves, so videoRef.current is still null at the
  // moment getUserMedia settles.
  useEffect(() => {
    if (permission === "granted" && videoRef.current && streamRef.current) {
      videoRef.current.srcObject = streamRef.current;
    }
  }, [permission]);

  const toggleCamera = useCallback(() => {
    const track = streamRef.current?.getVideoTracks()[0];
    if (!track) return;
    track.enabled = !track.enabled;
    setCameraOn(track.enabled);
  }, []);

  const toggleMic = useCallback(() => {
    const track = streamRef.current?.getAudioTracks()[0];
    if (!track) return;
    track.enabled = !track.enabled;
    setMicOn(track.enabled);
    if (!track.enabled) setMicLevel(0);
  }, []);

  const handleJoin = useCallback(() => {
    // Release before navigating. The interview page re-acquires its own stream, and the
    // permission grant persists for the origin, so this is instant and promptless —
    // whereas handing a live MediaStream across a route change leaks it whenever the
    // navigation is abandoned.
    releaseDevices();
    onJoin();
  }, [onJoin, releaseDevices]);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Left — device preview */}
        <div className="space-y-3">
          <div className="relative aspect-video overflow-hidden rounded-xl bg-foreground">
            {permission === "granted" && cameraOn ? (
              <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                className="size-full object-cover"
              />
            ) : (
              <div className="flex size-full flex-col items-center justify-center gap-2 px-6 text-center">
                <VideoOff className="size-8 text-muted-foreground" />
                <p className="text-sm font-medium text-muted-foreground">
                  {permission === "granted" && !cameraOn
                    ? "Camera is off"
                    : permission === "denied"
                      ? "Camera and microphone blocked"
                      : permission === "no-device"
                        ? "No camera or microphone found"
                        : permission === "unsupported"
                          ? "This browser can't access media devices"
                          : "Starting camera…"}
                </p>
                {permission === "denied" && (
                  <p className="max-w-xs text-xs text-muted-foreground">
                    Allow access in your browser&apos;s address bar to see
                    yourself. You can still join and answer by typing.
                  </p>
                )}
                {permission === "no-device" && (
                  <p className="max-w-xs text-xs text-muted-foreground">
                    You can still join - this interview works entirely by text.
                  </p>
                )}
                {errorDetail && (
                  <p className="max-w-xs text-xs text-muted-foreground">
                    {errorDetail}
                  </p>
                )}
              </div>
            )}
          </div>

          <div className="flex items-center gap-3">
            <Button
              type="button"
              variant={cameraOn ? "secondary" : "destructive"}
              size="sm"
              onClick={toggleCamera}
              disabled={permission !== "granted"}
            >
              {cameraOn ? (
                <Video className="size-4" />
              ) : (
                <VideoOff className="size-4" />
              )}
              <span className="ml-1.5">
                {cameraOn ? "Camera on" : "Camera off"}
              </span>
            </Button>

            <Button
              type="button"
              variant={micOn ? "secondary" : "destructive"}
              size="sm"
              onClick={toggleMic}
              disabled={permission !== "granted"}
            >
              {micOn ? (
                <Mic className="size-4" />
              ) : (
                <MicOff className="size-4" />
              )}
              <span className="ml-1.5">{micOn ? "Mic on" : "Mic off"}</span>
            </Button>

            {/* Level meter — the only way to tell a working mic from a silent one
 before the interview starts. */}
            <div
              className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted"
              aria-hidden="true"
            >
              <div
                className="h-full rounded-full bg-success transition-[width] duration-75"
                style={{ width: `${Math.round(micLevel * 100)}%` }}
              />
            </div>
          </div>
        </div>

        {/* Right — what the interview will cover */}
        <Card className="flex flex-col">
          <CardContent className="flex-1 space-y-3 pt-6">
            <div>
              <h3 className="font-heading text-base font-semibold text-foreground">
                {title}
              </h3>
              <p className="text-xs text-muted-foreground">
                {roleTitle ? `${roleTitle} · ` : ""}
                {topics.length} topic{topics.length === 1 ? "" : "s"}
              </p>
              {/* Deliberately describes topics as an outline, not a question list. The
 interviewer generates each question live from the topic and adapts to
 the answer — a weak answer earns one follow-up before moving on
 (services/agents/assessment/interview_graph.py), so the number of
 questions is not fixed and the wording is never pre-written. */}
              <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                This outline sets the agenda - it isn&apos;t a script. Every
                question is written live from your answers, and a thin answer
                earns a follow-up on the same topic before moving on.
              </p>
            </div>

            <ol className="space-y-2">
              {topics.map((topic, index) => (
                <li
                  key={`${index}-${topic}`}
                  className="flex gap-3 rounded-md border border-border bg-card p-3"
                >
                  <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-meta font-bold text-primary">
                    {index + 1}
                  </span>
                  <span className="text-sm font-medium text-foreground">
                    {topic}
                  </span>
                </li>
              ))}
            </ol>
          </CardContent>
        </Card>
      </div>

      <div className="flex items-center justify-between gap-3">
        <Button
          type="button"
          variant="ghost"
          onClick={onBack}
          disabled={joining}
        >
          <ArrowLeft className="mr-1.5 size-4" />
          Back
        </Button>

        {/* Never blocked on device permission: the interview is fully answerable by
 text, so refusing to start without a camera would strand people whose
 hardware or browser settings we can't fix for them. */}
        <Button type="button" onClick={handleJoin} disabled={joining}>
          {joining ? (
            <>
              <Loader2 className="mr-1.5 size-4 animate-spin" />
              Starting…
            </>
          ) : (
            "Join interview"
          )}
        </Button>
      </div>
    </div>
  );
}
