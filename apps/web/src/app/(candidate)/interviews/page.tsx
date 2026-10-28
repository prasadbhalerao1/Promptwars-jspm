"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";
import { useAsyncResource } from "@/hooks/useAsyncResource";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Page, PageHeader } from "@/components/common/PageHeader";
import { SectionError } from "@/components/common/SectionError";
import { InterviewLobby } from "@/components/interview/InterviewLobby";
import {
  fetchOpenInterviewDefinitions,
  generateDefinitionQuestions,
  startInterview,
  type InterviewDefinitionQuestion,
  type InterviewDefinitionResponse,
} from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

export default function CandidateInterviewsPage() {
  const router = useRouter();
  const { getToken } = useAuth();

  // Practice interview creation state
  const [showCreatePractice, setShowCreatePractice] = useState(false);
  const [practiceRole, setPracticeRole] = useState("");
  const [practiceDesc, setPracticeDesc] = useState("");
  const [practiceYears, setPracticeYears] = useState("");
  const [practiceQuestions, setPracticeQuestions] = useState<
    InterviewDefinitionQuestion[]
  >([]);
  const [generatingPractice, setGeneratingPractice] = useState(false);

  // Navigation
  const [startingSession, setStartingSession] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // The device-check lobby both entry points pass through. `definitionId` is null for a
  // generated practice interview (which starts from a topic_plan instead).
  const [lobby, setLobby] = useState<{
    definitionId: string | null;
    title: string;
    roleTitle?: string;
    topics: string[];
  } | null>(null);

  // Previously swallowed every failure and rendered "no open interviews", so a
  // candidate with invitations waiting saw an empty page and no way to retry.
  const definitionsFetcher = useCallback(async () => {
    const token = await getToken();
    if (!token) throw new Error("No session token");
    return fetchOpenInterviewDefinitions(token);
  }, [getToken]);

  const {
    data: fetchedDefinitions,
    error: definitionsError,
    loading: loadingDefinitions,
    retry: retryDefinitions,
  } = useAsyncResource(definitionsFetcher, "candidate:open-interviews");

  const openDefinitions = fetchedDefinitions ?? [];

  async function handleGeneratePracticeQuestions(e: React.FormEvent) {
    e.preventDefault();
    if (!practiceRole || !practiceDesc) return;

    setGeneratingPractice(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("No session token");

      const result = await generateDefinitionQuestions(token, {
        role_title: practiceRole,
        job_description: practiceDesc,
        years_experience: practiceYears ? Number(practiceYears) : undefined,
        question_count: 5,
      });

      setPracticeQuestions(result.questions);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to generate practice topics",
      );
    } finally {
      setGeneratingPractice(false);
    }
  }

  /** Opens the lobby for a recruiter-published definition. This used to call
   * startInterview() directly on click, so the candidate was dropped into a live
   * session with no chance to check their camera or mic first. */
  function openDefinitionLobby(definition: InterviewDefinitionResponse) {
    setError(null);
    setLobby({
      definitionId: definition.id,
      title: definition.title,
      roleTitle: definition.role_title,
      topics: definition.questions.map((q) => q.topic),
    });
  }

  function openPracticeLobby() {
    if (practiceQuestions.length === 0) {
      setError("No topics generated");
      return;
    }
    setError(null);
    setLobby({
      definitionId: null,
      title: "Practice interview",
      roleTitle: practiceRole || undefined,
      topics: practiceQuestions.map((q) => q.topic),
    });
  }

  /** Single join path for both entry points — the session is only created once the
   * candidate has actually passed the device check. */
  async function handleJoinFromLobby() {
    if (!lobby) return;
    setStartingSession(lobby.definitionId ?? "practice");
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("No session token");

      const result = await startInterview(
        token,
        lobby.definitionId
          ? { interview_definition_id: lobby.definitionId }
          : { topic_plan: lobby.topics },
      );
      // router.push, not window.location.href: a full document reload throws away
      // the whole React tree and re-downloads the bundle just to change route.
      router.push(`/interview/${result.session_id}`);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to start interview",
      );
      setStartingSession(null);
    }
  }

  // The lobby takes over the page rather than rendering inside the browse list: it owns
  // a live camera preview, and keeping the rest of the page mounted behind it invites
  // the user to navigate away with the stream still running.
  if (lobby) {
    return (
      <Page>
        <PageHeader
          title="Ready to join?"
          description="Check your camera and microphone before you start."
        />

        {error && (
          <p role="alert" className="mb-4 text-body text-destructive">
            {error}
          </p>
        )}

        <InterviewLobby
          topics={lobby.topics}
          title={lobby.title}
          roleTitle={lobby.roleTitle}
          joining={startingSession !== null}
          onJoin={handleJoinFromLobby}
          onBack={() => {
            setLobby(null);
            setError(null);
          }}
        />
      </Page>
    );
  }

  return (
    <Page>
      <PageHeader
        title="Interviews"
        description="Take an interview a recruiter has published, or generate one to practise against."
      />

      <Card>
        <CardHeader>
          <CardTitle className="text-base font-semibold">
            Open interviews
          </CardTitle>
          <CardDescription>
            Templates recruiters have published for you to take.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {error && (
            <p role="alert" className="text-body text-destructive">
              {error}
            </p>
          )}
          {definitionsError && (
            <SectionError
              message={definitionsError}
              onRetry={retryDefinitions}
              retrying={loadingDefinitions}
            />
          )}
          {loadingDefinitions && !fetchedDefinitions && (
            /* Skeleton rows rather than a centred spinner: this was the last list in
               the app still using one, and a spinner gives no hint of the shape that
               is coming, so the layout jumps when data lands. The placeholders mirror
               the real row below — title, meta line, trailing action — at the same
               heights, so arrival is a swap rather than a reflow.
               `aria-busy` + a label carry the same announcement the spinner's
               aria-live did, so nothing is lost for screen readers. */
            <div className="space-y-3" aria-busy="true" aria-label="Loading open interviews">
              {Array.from({ length: 2 }).map((_, i) => (
                <div
                  key={i}
                  className="flex flex-col justify-between gap-4 rounded-md border bg-card p-4 shadow-flat sm:flex-row sm:items-center"
                >
                  <div className="flex-1 space-y-2">
                    <Skeleton className="h-4 w-2/5" />
                    <Skeleton className="h-3 w-1/4" />
                  </div>
                  <Skeleton className="h-8 w-20 shrink-0" />
                </div>
              ))}
            </div>
          )}
          {!loadingDefinitions && openDefinitions?.length === 0 && (
            <p className="text-sm text-muted-foreground">
              No open interviews yet. Try creating a practice interview below.
            </p>
          )}
          {!loadingDefinitions &&
            openDefinitions?.map((def) => (
              <div
                key={def.id}
                className="p-4 border rounded-md flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-card shadow-flat"
              >
                <div>
                  <h4 className="text-sm font-semibold text-foreground">
                    {def.title}
                  </h4>
                  {/* "topics", not "questions": the count is how many areas the
 interviewer will cover, and each one can spawn a follow-up when an
 answer is thin, so the number of questions asked is not fixed. */}
                  <p className="text-xs text-muted-foreground mt-1">
                    {def.role_title} · {def.question_count} topics ·{" "}
                    {def.years_experience ?? "Not specified"} years experience
                  </p>
                </div>
                <Button
                  size="sm"
                  onClick={() => openDefinitionLobby(def)}
                  disabled={startingSession === def.id}
                >
                  {startingSession === def.id ? "Starting…" : "Start"}
                </Button>
              </div>
            ))}
        </CardContent>
      </Card>

      {/* Practice Interview Creation */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base font-semibold">
            Practice Interview
          </CardTitle>
          <CardDescription>
            Create a custom interview for any role. Describe the position and
            we&apos;ll generate topics.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {!showCreatePractice ? (
            <Button
              className="w-full"
              variant="outline"
              onClick={() => setShowCreatePractice(true)}
            >
              Create Practice Interview
            </Button>
          ) : (
            <div className="space-y-4">
              {practiceQuestions.length === 0 ? (
                <form
                  onSubmit={handleGeneratePracticeQuestions}
                  className="space-y-4"
                >
                  <div className="space-y-1">
                    <Label htmlFor="practiceRole">Role Title</Label>
                    <Input
                      id="practiceRole"
                      required
                      placeholder="e.g. Frontend Engineer"
                      value={practiceRole}
                      onChange={(e) => setPracticeRole(e.target.value)}
                    />
                  </div>

                  <div className="space-y-1">
                    <Label htmlFor="practiceDesc">Role Description</Label>
                    <Textarea
                      id="practiceDesc"
                      required
                      placeholder="What does this role do? What skills matter?"
                      value={practiceDesc}
                      onChange={(e) => setPracticeDesc(e.target.value)}
                    />
                  </div>

                  <div className="space-y-1">
                    <Label htmlFor="practiceYears">Years of Experience</Label>
                    <Input
                      id="practiceYears"
                      type="number"
                      min={0}
                      placeholder="e.g. 3"
                      value={practiceYears}
                      onChange={(e) => setPracticeYears(e.target.value)}
                    />
                  </div>

                  <div className="flex gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      className="flex-1"
                      onClick={() => setShowCreatePractice(false)}
                    >
                      Cancel
                    </Button>
                    <Button
                      type="submit"
                      className="flex-1"
                      pending={generatingPractice}
                    >
                      {generatingPractice ? "Generating…" : "Generate Topics"}
                    </Button>
                  </div>
                </form>
              ) : (
                <div className="space-y-3">
                  <div>
                    <Label className="text-xs">Generated Topics</Label>
                    <div className="space-y-2 mt-2">
                      {practiceQuestions.map((q, idx) => (
                        <div
                          key={q.id}
                          className="p-3 border rounded-md bg-card"
                        >
                          <p className="text-xs text-muted-foreground">
                            Topic {idx + 1}
                          </p>
                          <p className="text-sm font-semibold text-foreground">
                            {q.topic}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="flex gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      className="flex-1"
                      onClick={() => {
                        setPracticeQuestions([]);
                        setPracticeRole("");
                        setPracticeDesc("");
                        setPracticeYears("");
                      }}
                    >
                      Start Over
                    </Button>
                    <Button
                      type="button"
                      className="flex-1"
                      onClick={openPracticeLobby}
                      disabled={startingSession === "practice"}
                    >
                      {startingSession === "practice"
                        ? "Starting…"
                        : "Continue"}
                    </Button>
                  </div>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </Page>
  );
}
