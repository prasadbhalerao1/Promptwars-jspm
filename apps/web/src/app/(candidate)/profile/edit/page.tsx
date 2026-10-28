"use client";

import { useAuth } from "@/components/AuthProvider";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ConflictResolver } from "@/components/ConflictResolver";
import { useCurrentUser } from "@/components/CurrentUserProvider";
import {
  GITHUB_INGESTION_STAGES,
  INGESTION_STAGES,
  StageProgress,
} from "@/components/common/StageProgress";
import {
  connectGithubUsername,
  connectLeetcode,
  fetchDashboard,
  fetchGithubOAuthUrl,
  pollIngestionStatus,
  uploadCertificate,
  uploadResume,
  updateProfile,
  publishPortfolio,
  addHackathonExperience,
  removeHackathonExperience,
  type CandidateProfileResponse,
  type HackathonExperienceResult,
} from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Page } from "@/components/common/PageHeader";

export default function ProfileEditPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isLoaded, isSignedIn, getToken } = useAuth();
  const { me } = useCurrentUser();
  const [profile, setProfile] = useState<CandidateProfileResponse | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  // Which ingestion phase the backend reports it is currently running. Drives the
  // stepwise progress list so a multi-minute GitHub crawl shows visible movement
  // instead of one frozen "analyzing…" line.
  const [ingestionStage, setIngestionStage] = useState<string | null>(null);
  const [githubInput, setGithubInput] = useState("");
  const [leetcodeInput, setLeetcodeInput] = useState("");
  const [usernameInput, setUsernameInput] = useState("");
  const resumeInputRef = useRef<HTMLInputElement>(null);
  const certificateInputRef = useRef<HTMLInputElement>(null);

  const hasInitialized = useRef(false);
  const [fullName, setFullName] = useState("");
  const [headline, setHeadline] = useState("");
  const [location, setLocation] = useState("");
  const [college, setCollege] = useState("");
  const [degree, setDegree] = useState("");

  const [hackathonName, setHackathonName] = useState("");
  const [hackathonResult, setHackathonResult] =
    useState<HackathonExperienceResult>("participant");
  const [hackathonWeight, setHackathonWeight] = useState(3);
  const [hackathonDate, setHackathonDate] = useState("");
  const [showHackathonForm, setShowHackathonForm] = useState(false);

  const reload = useCallback(async () => {
    const token = await getToken();
    if (!token) return;
    const dashboard = await fetchDashboard(token);
    setProfile(dashboard.profile);

    if (!hasInitialized.current) {
      if (dashboard.profile) {
        setHeadline(dashboard.profile.headline ?? "");
        setLocation(dashboard.profile.location ?? "");
        const edu = dashboard.profile.education?.[0] as
          { institution?: string; degree?: string } | undefined;
        setCollege(edu?.institution ?? "");
        setDegree(edu?.degree ?? "");
        setUsernameInput(dashboard.profile.username ?? "");
      }
      if (me?.profile) {
        setFullName(me.profile.full_name ?? "");
      }
      hasInitialized.current = true;
    }
  }, [getToken, me]);

  useEffect(() => {
    if (!isLoaded) return;
    if (!isSignedIn) {
      router.replace("/sign-in");
      return;
    }
    // Wait for the shared user context to resolve so reload()'s one-time fullName seed
    // (gated on hasInitialized) sees a real `me` instead of running early and being
    // skipped permanently on the next reload() call once `me` arrives.
    if (!me) return;

    let cancelled = false;
    (async () => {
      try {
        await reload();
      } catch (err) {
        if (!cancelled)
          setError(
            err instanceof Error ? err.message : "Failed to load profile",
          );
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [isLoaded, isSignedIn, me, router, reload]);

  useEffect(() => {
    const githubStatus = searchParams.get("github");
    if (!githubStatus) return;

    let cancelled = false;
    (async () => {
      if (githubStatus === "connected") {
        if (!cancelled) {
          setNotice("GitHub connected - analyzing your repositories…");
        }
        try {
          const token = await getToken();
          if (token) {
            // Refresh what we already have right away so the page renders the connected
            // profile instead of sitting blank for the whole crawl.
            await reload().catch(() => undefined);

            const result = await pollIngestionStatus(token, {
              onUpdate: (status) => {
                if (!cancelled && status.status === "processing") {
                  setNotice("GitHub connected - analyzing your repositories…");
                  setIngestionStage(status.stage ?? null);
                }
              },
            });
            if (!cancelled) {
              setIngestionStage(null);
              if (result.status === "failed") {
                setNotice(null);
                setError(result.error ?? "GitHub sync failed");
              } else if (result.status === "processing") {
                // Genuine timeout on a very large account — say so explicitly rather
                // than showing a stale profile that looks like nothing happened.
                setNotice(
                  "GitHub connected - still analyzing your repositories. Your Talent Score will update automatically; you can keep using the app.",
                );
              } else {
                setNotice("GitHub connected - Talent Score updated.");
              }
            }
          }
        } catch {
          // best-effort — the dashboard's own load will still reflect eventual state
        } finally {
          // Never leave a half-finished step list on screen if polling threw.
          if (!cancelled) setIngestionStage(null);
        }
        await reload().catch(() => undefined);
      } else if (!cancelled) {
        setError(`GitHub connection failed: ${githubStatus}`);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [searchParams, reload, getToken]);

  async function handleConnectGithubUsername() {
    if (!githubInput.trim()) return;
    setBusy("github");
    setError(null);
    setNotice("Connecting GitHub username and queuing analysis...");
    try {
      const token = await getToken();
      if (!token) throw new Error("No session token");
      const updated = await connectGithubUsername(token, githubInput.trim());
      setProfile(updated);
      setNotice("GitHub username connected — analyzing repositories...");
      setGithubInput("");
      const result = await pollIngestionStatus(token, {
        onUpdate: (status) => {
          if (status.status === "processing") {
            setIngestionStage(status.stage ?? null);
          }
        },
      });
      if (result.status === "failed") {
        setError(result.error ?? "GitHub analysis failed");
      } else {
        setNotice("GitHub connected — Talent Score updated!");
      }
      await reload();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not connect GitHub",
      );
    } finally {
      setBusy(null);
      setIngestionStage(null);
    }
  }

  async function handleConnectGithub() {
    setBusy("github");
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("No session token");
      const authorizeUrl = await fetchGithubOAuthUrl(token);
      window.location.href = authorizeUrl;
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not start GitHub connection",
      );
      setBusy(null);
    }
  }

  async function handleConnectLeetcode() {
    if (!leetcodeInput.trim()) return;
    setBusy("leetcode");
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("No session token");
      const updated = await connectLeetcode(token, leetcodeInput.trim());
      setProfile(updated);
      setNotice("LeetCode connected - problem-solving stats synced.");
      setLeetcodeInput("");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not connect LeetCode",
      );
    } finally {
      setBusy(null);
    }
  }

  async function handleResumeUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy("resume");
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("No session token");
      await uploadResume(token, file);
      // Ingestion (parsing + Talent Score recompute) now runs in the background —
      // the upload response returns immediately with ingestion_status: "processing".
      setNotice("Resume uploaded - processing in the background.");
      // Show the stored resume immediately; don't gate the whole page on the recompute.
      await reload().catch(() => undefined);
      const result = await pollIngestionStatus(token, {
        onUpdate: (status) => setIngestionStage(status.stage ?? null),
      });
      if (result.status === "failed") {
        setError(result.error ?? "Resume processing failed");
      } else if (result.status === "processing") {
        setNotice(
          "Resume uploaded - still processing. Your Talent Score will update shortly.",
        );
      } else {
        setNotice("Resume processed - Talent Score updated.");
      }
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Resume upload failed");
    } finally {
      setBusy(null);
      setIngestionStage(null);
      e.target.value = "";
    }
  }

  async function handleCertificateUpload(
    e: React.ChangeEvent<HTMLInputElement>,
  ) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy("certificate");
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("No session token");
      await uploadCertificate(token, file);
      setNotice("Certificate uploaded - processing in the background.");
      await reload().catch(() => undefined);
      const result = await pollIngestionStatus(token, {
        onUpdate: (status) => setIngestionStage(status.stage ?? null),
      });
      if (result.status === "failed") {
        setError(result.error ?? "Certificate processing failed");
      } else if (result.status === "processing") {
        setNotice(
          "Certificate uploaded - still scanning. Results will appear shortly.",
        );
      } else {
        setNotice("Certificate processed and OCR-scanned.");
      }
      await reload();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Certificate upload failed",
      );
    } finally {
      setBusy(null);
      setIngestionStage(null);
      e.target.value = "";
    }
  }

  async function handleSaveProfileInfo() {
    setBusy("save_profile");
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("No session token");
      const updated = await updateProfile(token, {
        full_name: fullName,
        headline: headline,
        location: location,
        college: college,
        degree: degree,
      });
      setProfile(updated);
      setNotice("Profile information updated successfully.");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to update profile information",
      );
    } finally {
      setBusy(null);
    }
  }

  async function handleSetUsername() {
    const trimmed = usernameInput.trim().toLowerCase();
    if (!trimmed) return;
    setBusy("username");
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("No session token");
      const updated = await publishPortfolio(token, trimmed);
      setProfile(updated);
      setNotice(
        `Portfolio username set to "${trimmed}". Your public link is now active.`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to set username");
    } finally {
      setBusy(null);
    }
  }

  async function handleAddHackathonExperience() {
    if (!hackathonName.trim() || !hackathonDate) return;
    setBusy("add_hackathon");
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("No session token");
      const updated = await addHackathonExperience(token, {
        name: hackathonName.trim(),
        result: hackathonResult,
        weight: hackathonWeight,
        date: hackathonDate,
      });
      setProfile(updated);
      setNotice(
        "Hackathon experience added - Talent Score updating in background.",
      );
      // Reset form
      setHackathonName("");
      setHackathonResult("participant");
      setHackathonWeight(3);
      setHackathonDate("");
      setShowHackathonForm(false);
      // Poll for rescore completion
      await pollIngestionStatus(token);
      await reload();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to add hackathon experience",
      );
    } finally {
      setBusy(null);
    }
  }

  async function handleRemoveHackathonExperience(entryId: string) {
    setBusy(`remove_hackathon_${entryId}`);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("No session token");
      const updated = await removeHackathonExperience(token, entryId);
      setProfile(updated);
      setNotice(
        "Hackathon experience removed - Talent Score updating in background.",
      );
      // Poll for rescore completion
      await pollIngestionStatus(token);
      await reload();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to remove hackathon experience",
      );
    } finally {
      setBusy(null);
    }
  }

  if (!profile) {
    /* Mirrors the loaded layout's wrapper and card exactly, so the page doesn't jump
       when the profile arrives — the previous bare "Loading your profile…" line sat at
       the top-left of an otherwise empty page and was replaced by a full-width card.
       `aria-busy` + label preserve the announcement that plain text gave. */
    return (
      <Page
        width="reading"
        className="space-y-6"
        aria-busy="true"
        aria-label="Loading your profile"
      >
        <Card>
          <CardHeader>
            <Skeleton className="h-5 w-48" />
          </CardHeader>
          <CardContent className="space-y-4">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="flex items-center justify-between gap-4">
                <div className="space-y-2">
                  <Skeleton className="h-4 w-24" />
                  <Skeleton className="h-3 w-36" />
                </div>
                <Skeleton className="h-8 w-24 shrink-0" />
              </div>
            ))}
          </CardContent>
        </Card>
      </Page>
    );
  }

  return (
    <Page width="reading" className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="font-heading">Connect your evidence</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {error && <p className="text-sm text-destructive">{error}</p>}
          {notice && <p className="text-sm text-muted-foreground">{notice}</p>}
          {ingestionStage && (
            <StageProgress
              stages={
                busy === "github" || Boolean(searchParams.get("github"))
                  ? GITHUB_INGESTION_STAGES
                  : INGESTION_STAGES
              }
              currentStage={ingestionStage}
              className="rounded-md border bg-muted/30 p-3"
            />
          )}

          <div className="flex flex-col gap-3 rounded-lg border border-border/50 p-3 bg-muted/10">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex-1">
                <p className="text-sm font-medium">GitHub</p>
                <p className="text-xs text-muted-foreground">
                  {profile.github_username
                    ? `Connected as ${profile.github_username}`
                    : "Not connected — enter username to analyze public repos, or connect via OAuth"}
                </p>
                <div className="flex items-center gap-2 mt-2">
                  <Input
                    value={githubInput}
                    onChange={(e) => setGithubInput(e.target.value)}
                    placeholder={profile.github_username ?? "GitHub username (e.g. torvalds)"}
                    className="max-w-64"
                  />
                  <Button
                    type="button"
                    onClick={handleConnectGithubUsername}
                    disabled={busy === "github" || !githubInput.trim()}
                    variant="default"
                    size="sm"
                  >
                    {busy === "github" ? "Syncing…" : "Sync Profile"}
                  </Button>
                </div>
              </div>
              <div className="flex sm:flex-col items-center sm:items-end justify-between gap-1 pt-2 sm:pt-0 border-t sm:border-t-0 border-border/40">
                <span className="text-[11px] text-muted-foreground">Or verify ownership:</span>
                <Button
                  type="button"
                  onClick={handleConnectGithub}
                  disabled={busy === "github"}
                  variant="outline"
                  size="sm"
                >
                  {profile.github_username ? "Reconnect OAuth" : "OAuth Connect"}
                </Button>
              </div>
            </div>
          </div>

          <div className="flex items-center justify-between gap-4">
            <div className="flex-1">
              <p className="text-sm font-medium">LeetCode</p>
              <p className="text-xs text-muted-foreground">
                {profile.leetcode_username
                  ? `Connected as ${profile.leetcode_username}`
                  : "Not connected"}
              </p>
              <Input
                value={leetcodeInput}
                onChange={(e) => setLeetcodeInput(e.target.value)}
                placeholder={profile.leetcode_username ?? "LeetCode username"}
                className="mt-2 max-w-52"
              />
            </div>
            <Button
              onClick={handleConnectLeetcode}
              disabled={busy === "leetcode" || !leetcodeInput.trim()}
              variant="outline"
            >
              {busy === "leetcode"
                ? "Connecting…"
                : profile.leetcode_username
                  ? "Reconnect"
                  : "Connect"}
            </Button>
          </div>

          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-sm font-medium">Resume</p>
              <p className="text-xs text-muted-foreground">PDF or DOCX</p>
            </div>
            <Button
              variant="outline"
              disabled={busy === "resume"}
              onClick={() => resumeInputRef.current?.click()}
            >
              {busy === "resume" ? "Uploading…" : "Upload résumé"}
            </Button>
            <input
              ref={resumeInputRef}
              type="file"
              accept=".pdf,.docx,.doc"
              className="hidden"
              onChange={handleResumeUpload}
            />
          </div>

          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-sm font-medium">Certificates</p>
              <p className="text-xs text-muted-foreground">Image or PDF</p>
            </div>
            <Button
              variant="outline"
              disabled={busy === "certificate"}
              onClick={() => certificateInputRef.current?.click()}
            >
              {busy === "certificate" ? "Scanning…" : "Upload certificate"}
            </Button>
            <input
              ref={certificateInputRef}
              type="file"
              accept="image/*,.pdf"
              className="hidden"
              onChange={handleCertificateUpload}
            />
          </div>
        </CardContent>
      </Card>

      <Card className="border-border bg-card text-foreground shadow-flat ">
        <CardHeader className="pb-3 border-b border-border">
          <CardTitle className="font-heading text-sm font-semibold tracking-wider text-muted-foreground uppercase">
            Edit Profile Details
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 pt-4">
          <div className="space-y-1.5">
            <label className="text-meta font-medium text-muted-foreground font-mono">
              Full Name
            </label>
            <Input
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="e.g. Jane Doe"
              className="border-border bg-card/30 focus-visible:ring-ring"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-meta font-medium text-muted-foreground font-mono">
              Headline
            </label>
            <Input
              value={headline}
              onChange={(e) => setHeadline(e.target.value)}
              placeholder="e.g. Senior Software Engineer"
              className="border-border bg-card/30 focus-visible:ring-ring"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-meta font-medium text-muted-foreground font-mono">
              Location
            </label>
            <Input
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="e.g. San Francisco, CA"
              className="border-border bg-card/30 focus-visible:ring-ring"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-meta font-medium text-muted-foreground font-mono">
                College / University
              </label>
              <Input
                value={college}
                onChange={(e) => setCollege(e.target.value)}
                placeholder="e.g. Stanford University"
                className="border-border bg-card/30 focus-visible:ring-ring"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-meta font-medium text-muted-foreground font-mono">
                Degree
              </label>
              <Input
                value={degree}
                onChange={(e) => setDegree(e.target.value)}
                placeholder="e.g. B.S. in Computer Science"
                className="border-border bg-card/30 focus-visible:ring-ring"
              />
            </div>
          </div>

          <Button
            onClick={handleSaveProfileInfo}
            disabled={busy === "save_profile"}
            className="mt-2 w-full"
          >
            {busy === "save_profile" ? "Saving..." : "Save Profile Details"}
          </Button>
        </CardContent>
      </Card>

      <ConflictResolver profile={profile} />

      {/* Hackathon Experience — self-reported external hackathon wins/placements */}
      <Card className="border-border bg-card text-foreground shadow-flat ">
        <CardHeader className="pb-3 border-b border-border">
          <CardTitle className="font-heading text-sm font-semibold tracking-wider text-muted-foreground uppercase">
            Hackathon Experience
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 pt-4">
          <p className="text-xs text-muted-foreground">
            Add hackathon wins, top-5 finishes, and other achievements from
            external hackathons. These contribute to your Talent Score.
          </p>

          {/* List of existing hackathon entries */}
          {profile.hackathon_experience &&
            profile.hackathon_experience.length > 0 && (
              <div className="space-y-2">
                {profile.hackathon_experience.map((entry) => (
                  <div
                    key={entry.id}
                    className="flex items-center justify-between gap-4 rounded-md border border-border bg-card/50 p-3"
                  >
                    <div className="flex-1">
                      <p className="text-sm font-medium text-foreground">
                        {entry.name}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {entry.result === "winner" && "Winner"}
                        {entry.result === "top5" && "Top 5"}
                        {entry.result === "finalist" && "Finalist"}
                        {entry.result === "participant" && "Participant"}
                        {" • "}
                        Importance: {entry.weight}/5 • {entry.date}
                      </p>
                      <p className="text-meta text-muted-foreground mt-1">
                        self-reported
                      </p>
                    </div>
                    <Button
                      onClick={() => handleRemoveHackathonExperience(entry.id)}
                      disabled={busy === `remove_hackathon_${entry.id}`}
                      variant="outline"
                      size="sm"
                      className="text-destructive hover:text-destructive"
                    >
                      Remove
                    </Button>
                  </div>
                ))}
              </div>
            )}

          {/* Add new hackathon entry form */}
          {!showHackathonForm ? (
            <Button
              onClick={() => setShowHackathonForm(true)}
              variant="outline"
              className="w-full"
            >
              + Add Hackathon Experience
            </Button>
          ) : (
            <div className="space-y-3 rounded-md border border-border bg-card/30 p-4">
              <div className="space-y-1.5">
                <label className="text-meta font-medium text-muted-foreground font-mono">
                  Hackathon Name
                </label>
                <Input
                  value={hackathonName}
                  onChange={(e) => setHackathonName(e.target.value)}
                  placeholder="e.g. HackIndia 2025, Smart India Hackathon"
                  className="border-border bg-card focus-visible:ring-ring"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label className="text-meta font-medium text-muted-foreground font-mono">
                    Result
                  </label>
                  <select
                    className="select-control"
                    value={hackathonResult}
                    onChange={(e) =>
                      setHackathonResult(
                        e.target.value as HackathonExperienceResult,
                      )
                    }
                  >
                    <option value="winner">Winner</option>
                    <option value="top5">Top 5</option>
                    <option value="finalist">Finalist</option>
                    <option value="participant">Participant</option>
                  </select>
                </div>

                <div className="space-y-1.5">
                  <label className="text-meta font-medium text-muted-foreground font-mono">
                    Importance (1-5)
                  </label>
                  <div className="flex items-center gap-2">
                    <input
                      type="range"
                      min="1"
                      max="5"
                      value={hackathonWeight}
                      onChange={(e) =>
                        setHackathonWeight(parseInt(e.target.value))
                      }
                      className="flex-1"
                    />
                    <span className="w-8 text-center text-sm font-medium text-foreground">
                      {hackathonWeight}
                    </span>
                  </div>
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="text-meta font-medium text-muted-foreground font-mono">
                  Date
                </label>
                <Input
                  type="date"
                  value={hackathonDate}
                  onChange={(e) => setHackathonDate(e.target.value)}
                  className="border-border bg-card focus-visible:ring-ring"
                />
              </div>

              <div className="flex gap-2">
                <Button
                  onClick={handleAddHackathonExperience}
                  disabled={
                    busy === "add_hackathon" ||
                    !hackathonName.trim() ||
                    !hackathonDate
                  }
                  className="flex-1"
                >
                  {busy === "add_hackathon" ? "Adding…" : "Add Experience"}
                </Button>
                <Button
                  onClick={() => {
                    setShowHackathonForm(false);
                    setHackathonName("");
                    setHackathonResult("participant");
                    setHackathonWeight(3);
                    setHackathonDate("");
                  }}
                  variant="outline"
                >
                  Cancel
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Portfolio Username — lets existing candidates set/change their URL slug */}
      <Card className="border-border bg-card text-foreground shadow-flat ">
        <CardHeader className="pb-3 border-b border-border">
          <CardTitle className="font-heading text-sm font-semibold tracking-wider text-muted-foreground uppercase">
            Portfolio Username
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 pt-4">
          <p className="text-xs text-muted-foreground leading-relaxed">
            Your unique public URL:{" "}
            <span className="font-mono text-primary">
              /{profile.username ?? "not set"}
            </span>
            {profile.username && (
              <a
                href={`/${profile.username}`}
                target="_blank"
                rel="noreferrer"
                className="ml-2 text-primary hover:underline"
              >
                View →
              </a>
            )}
          </p>
          <div className="flex items-center gap-2">
            <div className="flex flex-1 items-center rounded-md border border-border bg-card/30 ring-offset-background focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-1">
              <span className="select-none pl-3 text-sm text-muted-foreground">
                yourdomain.com/
              </span>
              <Input
                value={usernameInput}
                onChange={(e) =>
                  setUsernameInput(
                    e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""),
                  )
                }
                placeholder={profile.username ?? "yourname"}
                className="border-0 bg-transparent shadow-none focus-visible:ring-0 focus-visible:ring-offset-0 pl-1"
                autoComplete="off"
                spellCheck={false}
              />
            </div>
            <Button
              onClick={handleSetUsername}
              disabled={busy === "username" || !usernameInput.trim()}
              
            >
              {busy === "username"
                ? "Saving…"
                : profile.username
                  ? "Update"
                  : "Set Username"}
            </Button>
          </div>
          <p className="text-meta text-muted-foreground">
            Only lowercase letters, numbers, and hyphens. Min 2 chars.
          </p>
        </CardContent>
      </Card>

      <Button variant="link" onClick={() => router.push("/home")}>
        View your Talent Score →
      </Button>
    </Page>
  );
}
