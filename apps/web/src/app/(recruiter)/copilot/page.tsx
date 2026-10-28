"use client";

import { useRef, useState } from "react";
import { ArrowUp, Sparkles, UserRoundSearch } from "lucide-react";

import { Page, PageHeader } from "@/components/common/PageHeader";
import { EmptyState } from "@/components/common/EmptyState";
import { SectionError } from "@/components/common/SectionError";
import { MatchScore } from "@/components/common/MatchBreakdown";
import { useAuth } from "@/components/AuthProvider";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { postCopilotQuery, type CopilotResult } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/input";

/** Recruiter copilot: plain-language candidate search.
 *
 * Reworked from a generic chat bubble list. Three things were wrong with that version:
 * the panel described its own internals to the user ("Structured filters + Qdrant
 * semantic re-rank + Claude explanation, per doc 02 §3"), results were unclickable
 * `<li>` text so a promising candidate was a dead end, and the suggested queries were
 * static prose the user had to retype by hand.
 *
 * Multi-turn refinement already worked through `conversation_id`; it just was not
 * visible. Follow-ups are now offered explicitly, because progressive narrowing is the
 * actual workflow ("find React developers" then "only ones with hackathon experience").
 */

const STARTERS = [
  "Find full-stack engineers with verified Python and React",
  "Backend engineers with open-source contributions",
  "Candidates with hackathon experience in the last year",
] as const;

const REFINEMENTS = [
  "Only candidates with verified skills",
  "Narrow to the strongest problem solvers",
  "Show people who have shipped production apps",
] as const;

interface Turn {
  query: string;
  results: CopilotResult[];
}

export default function RecruiterCopilotPage() {
  const { getToken } = useAuth();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const inputRef = useRef<HTMLInputElement>(null);

  const started = turns.length > 0;

  async function run(query: string) {
    const trimmed = query.trim();
    if (!trimmed || searching) return;

    setInput("");
    setSearching(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("No session token");
      const response = await postCopilotQuery(token, trimmed, conversationId);
      setConversationId(response.conversation_id);
      setTurns((prev) => [...prev, { query: trimmed, results: response.results }]);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "The search could not be completed.",
      );
    } finally {
      setSearching(false);
    }
  }

  const latest = turns[turns.length - 1];

  return (
    <Page>
      <PageHeader
        title="Copilot search"
        description="Describe who you are looking for. Results are ranked across verified evidence, and every match shows what produced it."
      />

      <div className="space-y-6">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void run(input);
          }}
          className="flex gap-2"
        >
          <Input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={searching}
            aria-label="Describe the candidate you are looking for"
            placeholder={
              started
                ? "Refine these results, or start a new search"
                : "Find senior backend engineers with verified Go experience"
            }
            className="flex-1"
          />
          <Button type="submit" disabled={searching || !input.trim()}>
            <ArrowUp aria-hidden className="size-4" />
            Search
          </Button>
        </form>

        {/* Suggested queries are buttons, not prose to retype. */}
        <QueryChips
          label={started ? "Refine" : "Try a search"}
          queries={started ? REFINEMENTS : STARTERS}
          disabled={searching}
          onPick={(q) => void run(q)}
        />

        {error ? (
          <SectionError
            message={error}
            onRetry={() => void run(latest?.query ?? input)}
            retrying={searching}
          />
        ) : null}

        {searching ? <SearchingState /> : null}

        {!started && !searching && !error ? (
          <EmptyState
            icon={UserRoundSearch}
            title="No search yet"
            description="Describe a role in plain language. Copilot reads verified skills, project history and assessment results, then explains why each candidate ranks where it does."
          />
        ) : null}

        {turns
          .slice()
          .reverse()
          .map((turn, i) => (
            <TurnResults
              key={`${turn.query}-${turns.length - i}`}
              turn={turn}
              current={i === 0}
            />
          ))}
      </div>
    </Page>
  );
}

function QueryChips({
  label,
  queries,
  disabled,
  onPick,
}: {
  label: string;
  queries: readonly string[];
  disabled: boolean;
  onPick: (q: string) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-meta text-muted-foreground">{label}</span>
      {queries.map((q) => (
        <button
          key={q}
          type="button"
          disabled={disabled}
          onClick={() => onPick(q)}
          className={cn(
            "rounded-full bg-surface-sunken px-3 py-1.5 text-meta text-muted-foreground outline-none",
            "transition-colors duration-(--animate-duration-fast)",
            "hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50",
            "disabled:opacity-50",
          )}
        >
          {q}
        </button>
      ))}
    </div>
  );
}

function SearchingState() {
  return (
    <div className="space-y-3" aria-live="polite">
      <p className="flex items-center gap-2 text-meta text-muted-foreground">
        <Sparkles aria-hidden className="size-3.5" />
        Reading verified evidence across the candidate pool
      </p>
      {[0, 1, 2].map((i) => (
        <div key={i} className="rounded-md bg-card p-4 shadow-flat">
          <Skeleton className="h-4 w-48" />
          <Skeleton className="mt-2 h-3 w-full max-w-md" />
          <Skeleton className="mt-3 h-3 w-32" />
        </div>
      ))}
    </div>
  );
}

function TurnResults({ turn, current }: { turn: Turn; current: boolean }) {
  return (
    <section
      aria-label={`Results for ${turn.query}`}
      className={cn(!current && "opacity-70")}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-section font-semibold text-foreground">
          {turn.query}
        </h2>
        <span className="text-meta text-muted-foreground">
          {turn.results.length === 0
            ? "No matches"
            : `${turn.results.length} ${turn.results.length === 1 ? "candidate" : "candidates"}`}
        </span>
      </div>

      {turn.results.length === 0 ? (
        <EmptyState
          className="mt-3"
          icon={UserRoundSearch}
          title="No candidates matched"
          description="Try describing the role more broadly, or drop a requirement. Candidates appear here once they have evidence on file."
        />
      ) : (
        <ul className="mt-3 space-y-3">
          {turn.results.map((r) => (
            <li
              key={r.candidate_id}
              className="rounded-md bg-card p-4 shadow-flat"
            >
              <div className="flex items-start justify-between gap-4">
                <p className="min-w-0 text-body leading-relaxed text-muted-foreground">
                  {r.explanation}
                </p>
                <MatchScore value={r.match_percentage} className="shrink-0" />
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
