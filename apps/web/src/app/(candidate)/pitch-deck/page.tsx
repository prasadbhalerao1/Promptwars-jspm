"use client";

import { useAuth } from "@/components/AuthProvider";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { FileText, Upload } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { uploadPresentation } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Page, PageHeader } from "@/components/common/PageHeader";
import { cn } from "@/lib/utils";

// Doc/SRS/04 §2's actor table: "Candidate/Team uploads deck" — upload lives inside the
// (candidate) route group (guarded to role=candidate by this group's layout.tsx), same
// as profile/edit/page.tsx. The report VIEW (../[id]) is a separate route OUTSIDE any
// role group, since judges/recruiters/investors also need to view it per the SRS §1
// "fully self-contained, usable standalone" note — same "shared route, not per-role"
// pattern already established for /dashboard (see .agents/decisions.md).

const ACCEPTED = [".pptx", ".ppt", ".pdf"];
/** Matches the backend's own cap. Rejecting here saves the user a slow upload that was
 * always going to fail, and lets the message name the actual limit. */
const MAX_MB = 20;

export default function PitchDeckUploadPage() {
  const router = useRouter();
  const { getToken } = useAuth();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [linkedRepo, setLinkedRepo] = useState("");
  const [problemStatement, setProblemStatement] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  /** Client-side validation so a wrong file fails instantly with a specific reason,
   * rather than after a 20MB round trip with "Upload failed". */
  function validate(file: File): string | null {
    const name = file.name.toLowerCase();
    if (!ACCEPTED.some((ext) => name.endsWith(ext))) {
      return `That file type is not supported. Upload a PPTX, PPT or PDF.`;
    }
    if (file.size > MAX_MB * 1024 * 1024) {
      const mb = (file.size / (1024 * 1024)).toFixed(1);
      return `That deck is ${mb} MB. The limit is ${MAX_MB} MB, so try exporting it at a lower image quality.`;
    }
    return null;
  }

  async function upload(file: File) {
    const problem = validate(file);
    if (problem) {
      setError(problem);
      return;
    }

    setBusy(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("No session token");
      const { presentation_id } = await uploadPresentation(
        token,
        file,
        linkedRepo || undefined,
        problemStatement || undefined,
      );
      router.push(`/pitch-deck/${presentation_id}`);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "We could not upload that deck. Try again in a moment.",
      );
      setBusy(false);
    }
  }

  return (
    <Page width="reading" className="space-y-6">
      <PageHeader
        title="Pitch deck analyzer"
        description="Scored on problem clarity, innovation, business potential and technical feasibility, with a plagiarism and AI-content signal that is evidence for review rather than a verdict."
      />

      <Card>
        <CardHeader>
          <CardTitle>Upload a deck</CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="space-y-1.5">
            <Label htmlFor="problem-statement">
              Problem Statement / Challenge Brief (Optional)
            </Label>
            <Textarea
              id="problem-statement"
              rows={3}
              placeholder="e.g. Build an AI-powered talent intelligence platform with verifiable evidence and slide citations for hackathon judging..."
              value={problemStatement}
              onChange={(e) => setProblemStatement(e.target.value)}
              disabled={busy}
            />
            <p className="text-meta text-muted-foreground">
              Supplying the problem statement enables requirement coverage mapping, alignment scoring, and slide citations for each requirement.
            </p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="linked-repo">Linked repository (optional)</Label>
            <Input
              id="linked-repo"
              placeholder="owner/repo or https://github.com/owner/repo"
              value={linkedRepo}
              onChange={(e) => setLinkedRepo(e.target.value)}
              disabled={busy}
            />
            <p className="text-meta text-muted-foreground">
              Cross-checks the technical claims in the deck against your actual code.
            </p>
          </div>
          {/* Drag target doubles as the button, so there is one obvious place to act
              rather than a dropzone and a separate control competing for attention. */}
          <div
            onDragOver={(e) => {
              e.preventDefault();
              if (!busy) setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragging(false);
              if (busy) return;
              const file = e.dataTransfer.files?.[0];
              if (file) void upload(file);
            }}
            className={cn(
              "rounded-lg border border-dashed p-8 text-center transition-colors duration-(--animate-duration-fast)",
              dragging ? "border-primary bg-primary-muted" : "border-input",
              busy && "opacity-60",
            )}
          >
            {busy ? (
              <div aria-live="polite">
                <FileText
                  aria-hidden
                  className="mx-auto size-5 animate-pulse text-primary"
                />
                <p className="mt-3 text-body font-medium text-foreground">
                  Uploading your deck
                </p>
                <p className="mt-1 text-meta text-muted-foreground">
                  Analysis starts as soon as the file lands, and the report opens
                  on its own.
                </p>
              </div>
            ) : (
              <>
                <Upload aria-hidden className="mx-auto size-5 text-muted-foreground" />
                <p className="mt-3 text-body font-medium text-foreground">
                  Drop a deck here
                </p>
                <p className="mt-1 text-meta text-muted-foreground">
                  PPTX, PPT or PDF, up to {MAX_MB} MB
                </p>
                <Button
                  variant="outline"
                  className="mt-4"
                  onClick={() => fileInputRef.current?.click()}
                >
                  Choose a file
                </Button>
              </>
            )}
          </div>

          {error ? (
            <p role="alert" className="text-body text-destructive">
              {error}
            </p>
          ) : null}

          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPTED.join(",")}
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              e.target.value = "";
              if (file) void upload(file);
            }}
          />
        </CardContent>
      </Card>
    </Page>
  );
}
