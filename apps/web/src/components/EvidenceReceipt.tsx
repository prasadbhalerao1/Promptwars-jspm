"use client";

import { useState } from "react";
import { CheckCircle2, ChevronRight, ExternalLink, HelpCircle, Info, ShieldCheck, XCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { SUB_SCORE_LABELS, type SubScore, type TalentScoreResponse } from "@/lib/api";

const RUBRIC_LEVEL_NAMES: Record<number, string> = {
  1: "Foundational (Level 1)",
  2: "Developing (Level 2)",
  3: "Proficient (Level 3)",
  4: "Advanced (Level 4)",
  5: "Expert / Principal (Level 5)",
};

/** Evidence receipt with drill-down inspector.
 *
 * Recruiter and candidate can inspect observable indicators, provenance items,
 * explicit exclusions, and missing evidence for every competency score.
 */
export function EvidenceReceipt({ score }: { score: TalentScoreResponse }) {
  const [activeKey, setActiveKey] = useState<string | null>(null);

  const activeSubScore = activeKey ? score.sub_scores[activeKey] : null;
  const activeLabel = activeKey ? SUB_SCORE_LABELS[activeKey] || activeKey : "";

  return (
    <>
      <Card className="shadow-flat">
        <CardHeader className="mb-4 border-b border-border pb-3">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-section font-semibold text-foreground">
                Evidence Receipt & Rubric Audit
              </CardTitle>
              <p className="text-xs text-muted-foreground mt-0.5">
                Every rating is anchored to observable code/assessment indicators and source provenance
              </p>
            </div>
            <Badge variant="outline" className="text-xs font-mono">
              Registry v2.0
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-3 pt-0">
          {Object.entries(SUB_SCORE_LABELS).map(([key, label]) => {
            const sub = score.sub_scores[key];
            const wasRenormalized = score.renormalized_subscores.includes(key);
            const subValue = sub?.value;
            const pending = subValue === null || subValue === undefined;
            const status = pending
              ? "insufficient_evidence"
              : (sub?.status === "insufficient_evidence"
                  ? (subValue >= 40 ? "supported" : "partially_supported")
                  : (sub?.status || (subValue >= 40 ? "supported" : "partially_supported")));

            return (
              <div
                key={key}
                onClick={() => setActiveKey(key)}
                className="group cursor-pointer rounded-lg border border-border/60 p-3 hover:border-primary/40 hover:bg-muted/30 transition-colors"
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-foreground group-hover:text-primary transition-colors">
                      {label}
                    </span>
                    {sub?.rubric_level && (
                      <span className="text-xs font-mono px-1.5 py-0.5 rounded bg-muted text-muted-foreground border border-border/60">
                        L{sub.rubric_level}
                      </span>
                    )}
                    {status === "supported" && (
                      <Badge className="bg-success/10 text-success border border-success/20 text-xs px-1.5 py-0">
                        Supported
                      </Badge>
                    )}
                    {status === "partially_supported" && (
                      <Badge className="bg-warning/10 text-warning border border-warning/20 text-xs px-1.5 py-0">
                        Partially Supported
                      </Badge>
                    )}
                    {status === "insufficient_evidence" && (
                      <Badge variant="outline" className="text-xs px-1.5 py-0 text-muted-foreground">
                        Insufficient Evidence
                      </Badge>
                    )}
                  </div>

                  <div className="flex items-center gap-2">
                    {pending ? (
                      <span className="text-xs text-muted-foreground">
                        {wasRenormalized
                          ? "Weight redistributed"
                          : "Insufficient evidence"}
                      </span>
                    ) : (
                      <span
                        data-numeric
                        className="font-mono text-sm font-semibold text-foreground"
                      >
                        {sub.value?.toFixed(1)}
                      </span>
                    )}
                    <ChevronRight className="size-4 text-muted-foreground group-hover:translate-x-0.5 group-hover:text-primary transition-all" />
                  </div>
                </div>

                {sub?.rationale && (
                  <p className="mt-1 text-xs text-muted-foreground line-clamp-1">
                    {sub.rationale}
                  </p>
                )}
              </div>
            );
          })}
        </CardContent>
      </Card>

      {/* Competency Drill-Down Dialog */}
      <Dialog open={Boolean(activeKey)} onOpenChange={(open) => !open && setActiveKey(null)}>
        <DialogContent className="sm:max-w-lg max-h-[85vh] overflow-y-auto space-y-4">
          <DialogHeader>
            <div className="flex items-center justify-between pr-6">
              <DialogTitle className="text-base font-semibold font-heading">
                {activeLabel}
              </DialogTitle>
              {activeSubScore?.value !== null && activeSubScore?.value !== undefined ? (
                <div className="text-right">
                  <span className="font-mono text-lg font-bold text-foreground">
                    {activeSubScore.value.toFixed(1)}
                  </span>
                  <span className="text-xs text-muted-foreground"> / 100</span>
                </div>
              ) : null}
            </div>
            <DialogDescription className="text-xs text-muted-foreground">
              Competency Registry ID: <code className="font-mono text-foreground">{activeKey}</code> • Rubric v2.0
            </DialogDescription>
          </DialogHeader>

          {activeSubScore && (
            <div className="space-y-4 text-xs">
              {/* Rubric Anchor & Status */}
              <div className="rounded-lg bg-muted/40 p-3 border border-border/60 space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground font-medium">Rubric Anchor:</span>
                  <span className="font-semibold text-foreground">
                    {activeSubScore.rubric_level
                      ? RUBRIC_LEVEL_NAMES[activeSubScore.rubric_level] || `Level ${activeSubScore.rubric_level}`
                      : "Unassessed"}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground font-medium">Evidence Coverage:</span>
                  <span className="font-mono text-foreground">
                    {activeSubScore.evidence_coverage
                      ? `${(activeSubScore.evidence_coverage * 100).toFixed(0)}%`
                      : "0%"}
                  </span>
                </div>
              </div>

              {/* Rationale */}
              {activeSubScore.rationale && (
                <div className="space-y-1">
                  <p className="font-medium text-foreground">Evaluation Reasoning:</p>
                  <p className="text-muted-foreground leading-relaxed bg-muted/20 p-2.5 rounded border border-border/50">
                    {activeSubScore.rationale}
                  </p>
                </div>
              )}

              {/* Observable Indicators */}
              {activeSubScore.indicators && activeSubScore.indicators.length > 0 && (
                <div className="space-y-1.5">
                  <p className="font-medium text-foreground flex items-center gap-1.5">
                    <CheckCircle2 className="size-3.5 text-success" />
                    Observable Indicators Demonstrated:
                  </p>
                  <ul className="list-disc list-inside space-y-1 text-muted-foreground pl-1">
                    {activeSubScore.indicators.map((ind, i) => (
                      <li key={i}>{ind}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Source Provenance Items */}
              {activeSubScore.provenance_items && activeSubScore.provenance_items.length > 0 && (
                <div className="space-y-1.5">
                  <p className="font-medium text-foreground flex items-center gap-1.5">
                    <ShieldCheck className="size-3.5 text-primary" />
                    Source Provenance & Artifacts:
                  </p>
                  <div className="space-y-1.5">
                    {activeSubScore.provenance_items.map((prov, i) => (
                      <div key={i} className="rounded border border-border/60 p-2 bg-background/50 space-y-1">
                        <div className="flex items-center justify-between text-xs">
                          <span className="font-mono font-medium text-primary truncate max-w-xs">
                            {prov.source_id}
                          </span>
                          <span className="px-1.5 py-0.2 rounded bg-muted text-muted-foreground capitalize">
                            {prov.verification_status}
                          </span>
                        </div>
                        <p className="text-muted-foreground text-xs italic">
                          "{prov.excerpt}"
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Explicit Limitations / Exclusions */}
              {activeSubScore.limitations && activeSubScore.limitations.length > 0 && (
                <div className="space-y-1">
                  <p className="font-medium text-warning">
                    Explicit Limitations & Non-Inferences:
                  </p>
                  <ul className="list-disc list-inside space-y-0.5 text-muted-foreground pl-1">
                    {activeSubScore.limitations.map((lim, i) => (
                      <li key={i}>{lim}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Missing Evidence / Steps to improve */}
              {activeSubScore.missing_evidence && activeSubScore.missing_evidence.length > 0 && (
                <div className="space-y-1">
                  <p className="font-medium text-muted-foreground">
                    Missing Evidence (How to improve score):
                  </p>
                  <ul className="list-disc list-inside space-y-0.5 text-muted-foreground pl-1">
                    {activeSubScore.missing_evidence.map((me, i) => (
                      <li key={i}>{me}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
