"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
// GitBranch, not Github: lucide-react no longer ships brand icons.
import { ArrowLeft, ArrowRight, Check, FileText, GitBranch, Loader2, Upload } from "lucide-react";

import { useAuth } from "@/components/AuthProvider";
import { useCurrentUser } from "@/components/CurrentUserProvider";
import { Field } from "@/components/onboarding/Field";
import {
  OnboardingProgress,
  type WizardStep,
} from "@/components/onboarding/OnboardingProgress";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  connectLeetcode,
  fetchGithubOAuthUrl,
  fetchMyProfile,
  updateProfile,
  uploadResume,
  type CandidateProfileResponse,
} from "@/lib/api";
import { RESERVED_USERNAMES, USERNAME_PATTERN } from "@/lib/constants";

const STEPS: readonly WizardStep[] = [
  { id: "identity", title: "Identity", blurb: "How you appear to recruiters and public search." },
  {
    id: "background",
    title: "Background",
    blurb: "Where you studied and where you're based.",
  },
  {
    id: "connect",
    title: "Connect",
    blurb: "Evidence that powers your Talent Score.",
  },
];

type Values = {
  fullName: string;
  username: string;
  headline: string;
  college: string;
  degree: string;
  location: string;
  leetcode: string;
};

const EMPTY: Values = {
  fullName: "",
  username: "",
  headline: "",
  college: "",
  degree: "",
  location: "",
  leetcode: "",
};

/** Fields each step requires before it will advance. GitHub is deliberately absent:
 * it's required-but-skippable (see the step 3 copy), because a misconfigured or
 * rate-limited OAuth app would otherwise strand the user with no way into the app. */
const REQUIRED_BY_STEP: readonly (keyof Values)[][] = [
  ["fullName", "username", "headline"],
  ["college", "degree", "location"],
  [],
];

const LABELS: Record<keyof Values, string> = {
  fullName: "Full name",
  username: "Portfolio username",
  headline: "Headline",
  college: "College / University",
  degree: "Degree",
  location: "Location",
  leetcode: "LeetCode username",
};

export function OnboardingWizard() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isLoaded, isSignedIn, getToken } = useAuth();
  const { me, reload: reloadMe } = useCurrentUser();

  // Returning from GitHub OAuth lands on step 3 with ?github=connected, so the user
  // sees the result of what they just did instead of restarting at step 1.
  const githubParam = searchParams.get("github");
  const [step, setStep] = useState(() => (githubParam ? STEPS.length - 1 : 0));
  const [values, setValues] = useState<Values>(EMPTY);
  const [touched, setTouched] = useState(false);
  const [profile, setProfile] = useState<CandidateProfileResponse | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [resumeUploaded, setResumeUploaded] = useState(false);
  const [notice, setNotice] = useState<string | null>(
    githubParam === "connected"
      ? "GitHub connected - analyzing your repositories in the background."
      : null,
  );
  const [seeded, setSeeded] = useState(false);

  const role = me?.profile?.role;
  const isCandidate = role === "candidate";

  // Prefill from whatever already exists (name from signup, profile fields if the user
  // bailed mid-wizard and came back) so nobody retypes what the system already knows.
  useEffect(() => {
    if (!isLoaded || !isSignedIn || !me?.profile || seeded) return;

    let cancelled = false;
    (async () => {
      const fullName = me.profile?.full_name ?? "";
      if (!isCandidate) {
        if (!cancelled) {
          setValues((v) => ({ ...v, fullName }));
          setSeeded(true);
        }
        return;
      }
      try {
        const token = await getToken();
        if (!token || cancelled) return;
        const existing = await fetchMyProfile(token);
        if (cancelled) return;
        const edu = (existing.education?.[0] ?? {}) as {
          institution?: string;
          degree?: string;
        };
        setProfile(existing);
        setValues({
          fullName,
          username: existing.username ?? "",
          headline: existing.headline ?? "",
          college: edu.institution ?? "",
          degree: edu.degree ?? "",
          location: existing.location ?? "",
          leetcode: existing.leetcode_username ?? "",
        });
      } catch {
        // A profile row may not exist yet — that's the normal new-user case, not an
        // error worth showing. Fall back to just the name we already have.
        if (!cancelled) setValues((v) => ({ ...v, fullName }));
      } finally {
        if (!cancelled) setSeeded(true);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [isLoaded, isSignedIn, me, isCandidate, getToken, seeded]);

  useEffect(() => {
    if (isLoaded && !isSignedIn) router.replace("/sign-in");
  }, [isLoaded, isSignedIn, router]);

  const set = useCallback((key: keyof Values, value: string) => {
    setValues((v) => ({ ...v, [key]: value }));
  }, []);

  // Non-candidates have no /candidates/me to write to, so the background and connect
  // steps don't apply — they only confirm their name.
  const steps = useMemo(
    () => (isCandidate ? STEPS : STEPS.slice(0, 1)),
    [isCandidate],
  );

  const missing = useMemo(() => {
    const required = REQUIRED_BY_STEP[step] ?? [];
    return required.filter((key) => !values[key].trim());
  }, [step, values]);

  const saveProfile = useCallback(async () => {
    if (!isCandidate) return;
    const cleanUsername = values.username.trim().toLowerCase();
    if (cleanUsername) {
      if (RESERVED_USERNAMES.has(cleanUsername) || !USERNAME_PATTERN.test(cleanUsername)) {
        throw new Error("Username must be 3-40 lowercase characters (a-z, 0-9, hyphens).");
      }
    }
    const token = await getToken();
    if (!token) throw new Error("No session token");
    const updated = await updateProfile(token, {
      full_name: values.fullName.trim(),
      username: cleanUsername || undefined,
      headline: values.headline.trim(),
      location: values.location.trim(),
      college: values.college.trim(),
      degree: values.degree.trim(),
    });
    setProfile(updated);
  }, [getToken, isCandidate, values]);

  const finish = useCallback(async () => {
    setBusy("finish");
    setError(null);
    try {
      if (isCandidate) {
        await saveProfile();
        if (
          values.leetcode.trim() &&
          values.leetcode.trim() !== profile?.leetcode_username
        ) {
          // Optional and best-effort: a typo'd or private LeetCode handle must not
          // block someone from finishing onboarding.
          const token = await getToken();
          if (token)
            await connectLeetcode(token, values.leetcode.trim()).catch(
              () => undefined,
            );
        }
      }
      // /me is what every layout gates on, so it has to be refetched before leaving —
      // otherwise the cached `onboarding_required: true` bounces the user straight back.
      reloadMe();
      router.replace("/home");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Could not save your profile";
      if (msg.includes("username_taken")) {
        setError("That username is already taken. Please choose another portfolio handle.");
      } else {
        setError(msg);
      }
      setBusy(null);
    }
  }, [
    getToken,
    isCandidate,
    profile,
    reloadMe,
    router,
    saveProfile,
    values.leetcode,
  ]);

  const next = useCallback(async () => {
    setTouched(true);
    if (missing.length > 0) return;

    if (step === steps.length - 1) {
      await finish();
      return;
    }

    // Persist as we go, so a refresh or an OAuth detour never loses typed answers.
    setBusy("next");
    setError(null);
    try {
      await saveProfile();
      setTouched(false);
      setStep((s) => s + 1);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Could not save your details";
      if (msg.includes("username_taken")) {
        setError("That username is already taken. Please choose a different portfolio handle.");
      } else {
        setError(msg);
      }
    } finally {
      setBusy(null);
    }
  }, [finish, missing.length, saveProfile, step, steps.length]);

  const connectGithub = useCallback(async () => {
    setBusy("github");
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("No session token");
      // Save first: OAuth navigates away from this page entirely.
      await saveProfile();
      // "onboarding" brings the callback back here rather than /profile/edit.
      const authorizeUrl = await fetchGithubOAuthUrl(token, "onboarding");
      window.location.href = authorizeUrl;
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not start GitHub connection",
      );
      setBusy(null);
    }
  }, [getToken, saveProfile]);

  const handleResumeUpload = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy("resume");
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("No session token");
      await uploadResume(token, file);
      setResumeUploaded(true);
      setNotice("Resume uploaded! Ingesting skills and experience in the background.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to upload resume");
    } finally {
      setBusy(null);
    }
  }, [getToken]);

  if (!isLoaded || !me?.profile) {
    return (
      <div className="space-y-4">
        <div className="h-1.5 w-full animate-pulse rounded-full bg-muted" />
        <div className="h-64 animate-pulse rounded-xl bg-muted" />
      </div>
    );
  }

  const active = steps[step];
  const isLast = step === steps.length - 1;
  const githubConnected = Boolean(profile?.github_username);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-heading text-2xl font-semibold text-foreground">
          Set up your profile
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {isCandidate
            ? "This is what recruiters see, and what your Talent Score is built from."
            : "Just one detail before you get started."}
        </p>
      </div>

      <OnboardingProgress steps={steps} current={step} />

      <Card>
        <CardContent className="space-y-5 pt-6">
          <div>
            <h2 className="font-heading text-base font-semibold text-foreground">
              {active.title}
            </h2>
            <p className="text-sm text-muted-foreground">{active.blurb}</p>
          </div>

          {step === 0 && (
            <>
              <Field
                label={LABELS.fullName}
                value={values.fullName}
                onChange={(v) => set("fullName", v)}
                placeholder="e.g. Jane Doe"
                required
                autoFocus
                error={
                  touched && !values.fullName.trim()
                    ? "Your name is required."
                    : null
                }
              />

              <Field
                label={LABELS.username}
                value={values.username}
                onChange={(v) => set("username", v.toLowerCase().replace(/[^a-z0-9-]/g, ""))}
                placeholder="e.g. janedoe"
                required
                hint="Your unique handle at trace.dev/yourname"
                error={
                  touched && !values.username.trim()
                    ? "A portfolio username is required."
                    : touched && !USERNAME_PATTERN.test(values.username.trim())
                      ? "Use 3-40 lowercase letters, numbers, or hyphens."
                      : null
                }
              />

              <Field
                label={LABELS.headline}
                value={values.headline}
                onChange={(v) => set("headline", v)}
                placeholder="e.g. Final-year CS student - backend & distributed systems"
                required
                hint="One line on who you are and what you build."
                error={
                  touched && !values.headline.trim()
                    ? "A headline is required."
                    : null
                }
              />
            </>
          )}

          {step === 1 && (
            <>
              <Field
                label={LABELS.college}
                value={values.college}
                onChange={(v) => set("college", v)}
                placeholder="e.g. Stanford University"
                required
                autoFocus
                error={
                  touched && !values.college.trim()
                    ? "Your college is required."
                    : null
                }
              />
              <Field
                label={LABELS.degree}
                value={values.degree}
                onChange={(v) => set("degree", v)}
                placeholder="e.g. B.S. in Computer Science"
                required
                error={
                  touched && !values.degree.trim()
                    ? "Your degree is required."
                    : null
                }
              />
              <Field
                label={LABELS.location}
                value={values.location}
                onChange={(v) => set("location", v)}
                placeholder="e.g. Bengaluru, India"
                required
                error={
                  touched && !values.location.trim()
                    ? "Your location is required."
                    : null
                }
              />
            </>
          )}

          {step === 2 && (
            <>
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border p-4">
                <div className="min-w-0">
                  <p className="flex items-center gap-2 text-sm font-medium text-foreground">
                    <GitBranch className="size-4" />
                    GitHub
                  </p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {githubConnected
                      ? `Connected as ${profile?.github_username}`
                      : "The strongest signal in your Talent Score - we analyze your real commits."}
                  </p>
                </div>
                {githubConnected ? (
                  <span className="flex items-center gap-1.5 rounded-full bg-success/10 px-3 py-1 text-xs font-medium text-success">
                    <Check className="size-3.5" strokeWidth={3} />
                    Connected
                  </span>
                ) : (
                  <Button onClick={connectGithub} disabled={busy === "github"}>
                    {busy === "github" ? (
                      <>
                        <Loader2 className="mr-1.5 size-4 animate-spin" />
                        Redirecting…
                      </>
                    ) : (
                      "Connect GitHub"
                    )}
                  </Button>
                )}
              </div>

              <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border p-4">
                <div className="min-w-0">
                  <p className="flex items-center gap-2 text-sm font-medium text-foreground">
                    <FileText className="size-4" />
                    Resume PDF (Optional)
                  </p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {resumeUploaded
                      ? "Resume uploaded - extracting skills and history."
                      : "Upload a PDF resume to populate experience and skills automatically."}
                  </p>
                </div>
                {resumeUploaded ? (
                  <span className="flex items-center gap-1.5 rounded-full bg-success/10 px-3 py-1 text-xs font-medium text-success">
                    <Check className="size-3.5" strokeWidth={3} />
                    Uploaded
                  </span>
                ) : (
                  <label className="cursor-pointer">
                    <Button variant="outline" render={<span />} disabled={busy === "resume"}>
                      {busy === "resume" ? (
                        <>
                          <Loader2 className="mr-1.5 size-4 animate-spin" />
                          Uploading…
                        </>
                      ) : (
                        <>
                          <Upload className="mr-1.5 size-4" />
                          Upload PDF
                        </>
                      )}
                    </Button>
                    <input
                      type="file"
                      accept=".pdf"
                      className="sr-only"
                      onChange={handleResumeUpload}
                      disabled={busy === "resume"}
                    />
                  </label>
                )}
              </div>

              <Field
                label={LABELS.leetcode}
                value={values.leetcode}
                onChange={(v) => set("leetcode", v)}
                placeholder="e.g. janedoe"
                hint="Adds problem-solving stats to your public profile."
              />

              {!githubConnected && (
                <p className="text-xs text-muted-foreground">
                  You can skip GitHub for now - we&apos;ll keep reminding you on
                  your dashboard, and your Talent Score stays incomplete until
                  it&apos;s connected.
                </p>
              )}
            </>
          )}

          {error && <p className="text-sm text-destructive">{error}</p>}
          {notice && !error && <p className="text-sm text-success">{notice}</p>}

          <div className="flex items-center justify-between gap-3 pt-1">
            <Button
              variant="ghost"
              onClick={() => {
                setTouched(false);
                setNotice(null);
                setStep((s) => Math.max(0, s - 1));
              }}
              disabled={step === 0 || busy !== null}
            >
              <ArrowLeft className="mr-1.5 size-4" />
              Back
            </Button>

            <Button onClick={next} disabled={busy !== null}>
              {busy === "next" || busy === "finish" ? (
                <>
                  <Loader2 className="mr-1.5 size-4 animate-spin" />
                  Saving…
                </>
              ) : isLast ? (
                githubConnected ? (
                  "Finish"
                ) : (
                  "Skip for now & finish"
                )
              ) : (
                <>
                  Continue
                  <ArrowRight className="ml-1.5 size-4" />
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
