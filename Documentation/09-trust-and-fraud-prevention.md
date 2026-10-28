# Trust & Fraud Prevention System

## What it does (plain English)

This module answers one question for every piece of evidence a candidate submits: *is there a reason to doubt this, and if so, what exactly is that reason?* It never answers "is this candidate lying" directly — it produces evidence, not verdicts.

Concretely, it runs four independent detection subgraphs:

1. **Certificate verification** — is a claimed certification real? Checks the issuer against a trusted registry, tries to auto-verify against the issuer's own verification page when possible, and falls back to a conservative visual-plausibility check otherwise.
2. **Code/submission plagiarism** — does a candidate's assessment submission structurally match another candidate's, or a public GitHub repo?
3. **Duplicate profile detection** — does this candidate's profile text or photo match another account on the platform (the classic "one person, five accounts to farm more assessment attempts" pattern)?
4. **AI-generated content signal** — does a resume/profile section statistically look machine-generated?

Every signal computed — flagged or not — is written to an immutable `verification_records` table. When a signal crosses a threshold, it becomes a `fraud_flags` row with `status='raised'`. Nothing in the platform reacts to `raised` on its own; a human (admin or recruiter) has to review the evidence and explicitly move it to `upheld` (with written notes) or `dismissed`. Only `upheld` flags feed into a candidate's `AuthenticityScore`, which starts at 100 and loses points per upheld flag type.

Candidates can see every flag against themselves and file a dispute, which surfaces their explanation to the reviewer alongside an LLM-generated *neutral summary* of the dispute (never a recommendation).

## The problem it solves

Hiring platforms exist to convert claimed capability into hiring decisions. AI has made every input to that conversion trivially fakeable: LLMs write fluent, plausible resumes and cover letters in seconds; certificate templates are one Photoshop layer away from convincing; a candidate can clone someone else's GitHub-hosted solution to a take-home assessment and rename variables to dodge a naive text diff; and nothing stops one person from registering three accounts to game an assessment's retry limits or a hackathon's team-size rules.

A platform that scores "Talent" or "Fit" without also scoring "is any of this real" is optimizing for the wrong thing — it will rank a confident fabrication above an honest but less polished candidate. That's not a hypothetical edge case for this problem statement; the requirement explicitly names fake certificates, fake projects, AI-generated resumes, duplicate profiles, and plagiarized submissions as the things to catch, and asks for a Candidate Authenticity Score and Fraud Risk Reports as the deliverable, not just a paragraph in a proposal.

That's why this module is arguably the platform's strongest differentiator. A recruitment/hackathon tool without this is a slightly-better form. A tool that can say "we checked, here's the specific evidence, and here's what a human should look at" is the thing that makes every other score on the platform trustworthy. But the differentiation is honest, not oversold here: this is deterministic pattern-matching and heuristics wired to a human-review loop, not a forensics lab. That's a deliberate scope choice, discussed below.

## The core ethical design principle: flags never auto-affect anything

This is the design decision the rest of the module hangs off, and it's worth defending carefully because it's the one place a skeptical judge should push hardest.

**The problem with automatic fraud action.** Every detection mechanism here — MinHash text overlap, perceptual photo hashing, AST-based code similarity, a statistical AI-text heuristic, an issuer registry lookup — is a *heuristic*, not a proof. MinHash overlap can't distinguish "one candidate reworded another's resume" from "both candidates used the same LinkedIn-recommended headline template." A high AI-content score can't distinguish "fabricated" from "written by a non-native English speaker who leans on grammar-checking tools." Two candidates' code can overlap heavily because one copied the other, or because both correctly solved a narrow assessment problem the only reasonable way. None of these signals carry enough weight, alone, to end someone's opportunity — and doing so silently, via an automatic score penalty or automatic rejection, would mean a false positive costs a real person a real opportunity with no chance to explain themselves.

**The mechanism.** The codebase encodes this as a hard status machine on `FraudFlag` (`packages/db/models/fraud.py`):

- `raised` (the default, set the moment a detection subgraph's verdict crosses its threshold) — has **zero** effect on visibility, ranking, or `AuthenticityScore` anywhere else in the platform.
- `under_review` — set automatically the moment a candidate disputes a flag (`POST /flags/{id}/dispute` in `services/api/modules/fraud/router.py`); still has zero scoring effect.
- `upheld` — the only status that counts against `AuthenticityScore`. Reaching it requires a human reviewer to call `PATCH /flags/{id}/review`, and the router rejects the transition with a 422 (`review_notes_required_for_upheld`) if `review_notes` is empty or whitespace-only. There is no code path that sets `upheld` without a human explicitly writing why.
- `dismissed` — also human-set, also has zero scoring effect (correctly — a dismissed flag is a false positive, not a lesser offense).

The DB layer backs this up independently of the API: `fraud_flags.evidence` is `NOT NULL` at the column level (`Mapped[dict] = mapped_column(JSONB, nullable=False)`), so it is structurally impossible to construct a bare accusation with no evidence attached — even a future bug in the router that tried to create a flag without evidence would fail at the database, not just at a code-review checkpoint. That's belt-and-suspenders by design: the docstring in `fraud.py` says this explicitly — enforced at the DB/application layer, not just convention.

**Why non-empty `review_notes` matters as much as the evidence.** Requiring notes isn't paperwork for its own sake — it forces the reviewer to articulate, in their own words, why the automated evidence was sufficient in this specific case. That's the difference between "the algorithm said 82% similarity so I clicked uphold" and an actual accountable human decision that a specific person can be asked about later. It also means every upheld flag carries a natural-language audit trail a candidate (or a future auditor) can actually read, not just a similarity score.

**Why this is defensible, not just cautious.** A system that auto-penalizes on `raised` would be faster to build and would look more "automated" in a demo. It would also be indefensible the first time a heuristic false-positives on a legitimate candidate — and given what these specific heuristics are (statistical text scoring, hash-distance thresholds, substring issuer matching), false positives are not a remote edge case, they're an expected, routine occurrence. Building the review gate into the data model itself, rather than as an optional workflow step a developer could route around, is what makes the guarantee credible to an outside auditor rather than just a policy the team says it follows.

## The four detection subgraphs

All four are independent LangGraph subgraphs sharing one state shape (`services/agents/fraud/state.py`'s `FraudCheckState`): `subject_type`/`subject_id`, a router-prefetched `context` dict, an `operator.add`-reduced `signals` list, and a final `verdict`. Nodes are DB-free by convention — the router (`services/api/modules/fraud/router.py`) fetches everything a node needs before invoking the graph and persists whatever comes back (`_persist_check_result`), so the detection logic itself is pure, easily unit-testable, and cannot accidentally touch data it wasn't given.

### Certificate verification (`cert_graph.py`)

```
issuer_lookup --[resolvable]-------> auto_verify --------> cert_verdict --> END
issuer_lookup --[not resolvable]---> visual_forensics ----> cert_verdict --> END
```

`issuer_lookup` (`nodes/issuer_lookup.py` / `tools/issuer_lookup.py`) checks the candidate-entered issuer against the trusted-issuer registry (detailed below) and, if a verification URL resolves, the graph routes to `auto_verify` — a simple, deterministic check: does the credential ID appear verbatim on the fetched page? `verified` is `True`, `False`, or `None` ("couldn't determine," e.g. non-200 response) — it is never guessed `True` from an ambiguous signal.

If there's no automated verification path, the graph routes to `visual_forensics` (`tools/visual_forensics.py`) instead: a rules-based check first (missing issuer/title/credential ID, low OCR confidence — each adds a suspicion point, ≥3 points is "high"), optionally escalated by a Haiku vision pass over the certificate image if `ANTHROPIC_API_KEY` is configured and a public URL exists. The vision pass is a best-effort *enhancement layered on a working rules baseline* — if it's unavailable, the rules-only signal stands alone, capped at "low" confidence in the signal itself since it's metadata-only. When both ran, the code takes the *higher* of the two suspicion labels, never averages — a conservative asymmetry: don't let a benign-looking vision pass quietly cancel out a rules-based anomaly.

`cert_verdict.py` combines whichever branch ran into one verdict; only a confirmed non-match or a "high" visual suspicion crosses the flag-raising bar. An inconclusive/unreachable check is still recorded (full evidence trail via `verification_records`) but never accuses anyone. Full trace-through of the newly rewritten `confirmed_genuine` logic is in the next section.

### Code/submission plagiarism (`plagiarism_graph.py`)

```
structural_similarity --> public_repo_crosscheck --> plagiarism_verdict --> END
```

`structural_similarity.py` uses `copydetect`, an AST-winnowing/token-fingerprinting structural clone detector (the same family of algorithm as Stanford's MOSS or Dolos) — **deliberately not raw text diff and not embeddings.** The reasoning is explicit in the module's own docstring: this technique is "robust to variable renaming, unlike raw text diff." A candidate who copies another's solution and mechanically renames every variable and reorders a few statements defeats a text diff instantly; AST-winnowing fingerprints the token structure, not the literal characters, so that evasion doesn't work. The similarity score is the max of the two Jaccard-like overlap ratios `copydetect` returns (since each file has a different total token count), flagged at `>0.75`.

`public_repo_crosscheck.py` searches GitHub's public code-search API for a distinctive literal snippet from the submission, explicitly excluding matches in the candidate's own repos (their own code is not evidence of copying someone else's). It degrades to an empty, explicitly-labeled-inconclusive result on any API failure (rate limits are common on unauthenticated search) rather than reporting "no match found" with false confidence.

`plagiarism_verdict.py` treats a structural match above threshold as sufficient on its own to flag — unlike a purely statistical heuristic, a direct pairwise structural comparison against a specific other candidate's submission *is* concrete evidence, not just a suspicion signal. GitHub cross-check matches are additional corroborating evidence attached to the same flag.

### Duplicate profile detection (`duplicate_graph.py`)

```
text_fingerprint --> photo_hash --> duplicate_verdict --> END
```

`text_fingerprint.py` uses MinHash/Jaccard (via `datasketch`) over word-level 3-shingles — explicitly **not an embedding call**, and the docstring states the reasoning directly: this targets near-duplicate text ("same person, reworded slightly"), which MinHash/Jaccard answers well without an extra embedding-model round trip; an embedding-similarity term would catch *semantically* similar text (two different backend engineers describing similar work), which is not the fraud pattern being hunted here and would produce far more false positives across unrelated candidates who happen to share a domain vocabulary.

`photo_hash.py` uses perceptual hashing (`imagehash`'s pHash, DCT-based, 64-bit) — deliberately **not facial recognition**. The docstring is explicit about why: perceptual hashing detects literal image reuse (the same photo file, or a lightly re-encoded version of it, uploaded to two accounts), not biometric identity, which keeps this outside GDPR/BIPA special-category biometric-data territory. It uses a plain center-crop with no face-detection/alignment step — an earlier draft added alignment and that was deliberately walked back, per the module's own comment, to avoid the tool trying to do face-matching by another name. There's also a hand-maintained blacklist for common default/placeholder avatar hashes, so candidates who never uploaded a real photo aren't all flagged as duplicates of each other.

Both nodes run **sequentially**, not fanned out in parallel as doc 06's original mermaid diagram shows them — the docstring in `duplicate_graph.py` explains this is to sidestep a real LangGraph pitfall: `context` is a plain-overwrite channel (only `signals` uses the `operator.add` reducer), so two nodes writing to `context` in the same superstep would collide. Since `imagehash`/`datasketch` are both fast local computations with no network calls, there's no real latency cost to running them sequentially instead.

`duplicate_verdict.py` flags on *either* signal crossing its threshold independently (`SIMILARITY_FLAG_THRESHOLD=0.80` for text, Hamming distance `≤4`/64 bits for photo) — each is real pairwise evidence against a specific other candidate, so either alone is sufficient; confidence is escalated to "high" only when both signals corroborate the same conclusion.

### AI-generated content signal (`content_graph.py`)

```
perplexity_heuristic --> END
```

The simplest of the four — one node, no combination step. `perplexity_heuristic.py` deliberately reuses `ppt_analyzer/tools/ai_content_heuristic.py`'s private per-text scoring function rather than re-deriving a burstiness/lexical-diversity formula a second time, so the platform's two AI-content detectors (this one, and the PPT Analyzer's) agree on what "AI-generated-sounding text" means instead of silently diverging.

The node itself is the most conservative of the four by explicit design: it **never raises a flag on its own, even at a high score.** `should_flag` is hardcoded `False` in `nodes/perplexity_heuristic.py` regardless of the computed score; the signal is recorded via `verification_records` for a human (or a corroborating signal) to weigh, but this subgraph alone cannot put a `fraud_flags` row in the review queue. The rationale documented in the module: statistical AI-text detectors have a well-known false-positive problem for non-native-English writers and heavily templated resume text, so treating a bare high score as flag-worthy would systematically penalize a group of candidates for writing style, not fraud.

## The trusted issuer registry (the newest piece)

This is the part of the module that was just rebuilt this session, replacing a hardcoded 6-entry Python dict (`_ISSUER_VERIFY_URL_TEMPLATES` in the old `issuer_lookup.py`) with a real `trusted_issuers` database table, admin-manageable via `services/api/modules/fraud/router.py`'s `/admin/trusted-issuers` CRUD endpoints and the new `apps/web/src/app/(admin)/trusted-issuers/page.tsx` UI.

**Why a hardcoded dict was a real problem, not just an aesthetic one.** Every new legitimate issuer — a university, a smaller bootcamp, an employer-issued credential — required a code change and a deploy to add. That's not just an inconvenience; it silently strengthened the platform's *false-positive* rate over time, since every issuer a hackathon judge's own resume might legitimately cite that wasn't in the dict fell through to Visual Forensics with no way for anyone (other than an engineer touching the source file) to fix it. A registry that a non-technical admin can edit is the difference between a system that adapts to reality and one that only tracks what its last code freeze happened to include.

**The table** (`packages/db/models/fraud.py::TrustedIssuer`): `name` (unique), `aliases` (JSONB list), `verification_url_template` (nullable — an issuer can be trusted/known without an automated verification path, e.g. no public credential-lookup page exists), `trust_tier` (`platform`/`university`/`employer`/`community`, DB-constrained), `notes`, and `added_by_user_id` for accountability. The baseline migration creates it and `scripts/seed_db.py` seeds it with the same 6 issuers the old dict had (Coursera, freeCodeCamp, AWS, Credly, Udemy, HackerRank), so nothing regressed on deploy — existing recognized issuers stayed recognized.

**Matching logic** (`resolve_issuer` in `tools/issuer_lookup.py`): case-insensitive substring matching, checked against both the canonical `name` and every alias — a candidate entering "Amazon Web Services (AWS)" still matches the "AWS" registry row because the alias "aws" is checked as a substring in both directions (`name in key or key in name`). This preserves the old dict's matching flexibility exactly; the registry swap changed *where* the data lives, not the matching semantics candidates already experienced.

**The `is_recognized_issuer` vs `resolvable` distinction is the crux of the redesign.** These are now independently tracked, and conflating them was exactly the bug the rewrite fixed:

- `is_recognized_issuer` — did the candidate's entered issuer text match *any* row in the registry (by name or alias)?
- `resolvable` — does the matched row (if any) have a `verification_url_template` *and* a credential ID to fill it with, so an automated HTTP check can actually run?

An issuer can be recognized-but-not-resolvable (a known, legitimate issuer registered in the table, but with no automated verification page configured yet — falls through to Visual Forensics exactly as before, *without* any extra penalty, since "known but not URL-verifiable" is a fundamentally different fact from "we've never heard of this issuer"). An issuer can also be neither — not in the registry at all — and *that* case is new: it's now its own explicit, elevated-risk signal.

**Tracing `cert_verdict.py`'s `confirmed_genuine` guard exactly**, since this is the logic that determines when "unrecognized issuer" actually fires:

1. `confirmed_genuine` starts `False`.
2. If `auto_verify_result` exists and `verified is False` → immediate `fake_certificate` flag, return early. `confirmed_genuine` is never reached/set in this branch (doesn't matter — the function already returned).
3. If `auto_verify_result` exists and `verified` is truthy (i.e., positively matched) → `confirmed_genuine = True`, and a non-flagging verdict is built (but not returned yet — the unrecognized-issuer check still runs on it).
4. Else if `visual_result` exists and `suspicion_label == "high"` → immediate flag, return early. Same as step 2, `confirmed_genuine` stays `False` but it's moot.
5. Else if `visual_result` exists with lower suspicion → a non-flagging verdict is built. **Critically, `confirmed_genuine` stays `False` here** — the docstring is explicit about why: a visual-forensics pass, even a "low" suspicion one, is "not obviously fake," not a positive confirmation. Visual forensics has no ground-truth genuine template to compare against (it's a heuristic vision pass), so it structurally cannot promote a certificate to confirmed-genuine the way an actual credential-ID match on the issuer's own page can.
6. After either non-early-return branch, one more check runs: if `not confirmed_genuine` and `issuer_lookup_result.is_recognized_issuer is False` → override the verdict with a new `unrecognized_issuer` flag (medium confidence), citing the issuer-lookup evidence plus an explicit note that no other check positively confirmed the certificate as genuine.

So the only way "unrecognized issuer" is *suppressed* is a genuine auto-verify match (step 3) — the strongest, most concrete evidence available. A "low suspicion, no vision pass ran" visual-forensics result does **not** suppress it, because that path never had the standing to confirm anything in the first place. This asymmetry is deliberate: it stops the weakest positive signal (a vision pass that merely failed to spot forgery) from silently absorbing a distinct, independently meaningful negative signal (an issuer the platform has never vetted).

**Why this beats the old hardcoded-dict approach for a real deployment.** The old dict had no way to represent "we don't recognize this issuer" as anything other than "no automated verification path" — both cases fell through to Visual Forensics identically, meaning a candidate citing a completely fabricated issuer name got exactly the same treatment as one citing a real, well-known university that simply lacked a scripted verification URL. The registry doesn't just move data to a table — it introduces a genuinely new fraud signal (`unrecognized_issuer`) that didn't exist in the old design, at a correctly calibrated (lower) severity, entirely admin-configurable without a deploy.

## How the Authenticity Score works

The formula (`tools/aggregation.py::compute_authenticity_score`) is deliberately simple and fully transparent:

```
AuthenticityScore = max(0, 100 - sum(penalty[flag.flag_type] for flag in upheld_flags))
```

Penalty table:

| Flag type | Penalty |
|---|---|
| `duplicate_profile` | 40.0 |
| `code_plagiarism` | 35.0 |
| `fake_certificate` | 30.0 |
| `ai_generated_content` | 15.0 |
| `unrecognized_issuer` | 10.0 |
| unknown/unmapped type | 10.0 (never zero) |

Only `upheld` flags count — a `raised` flag sitting in the review queue contributes nothing, per the ethical design principle above. The function itself has no way to check a flag's status (it takes a pre-filtered list), so the burden of correctness is placed on the caller (`services/api/modules/fraud/router.py::get_authenticity_score`), which explicitly filters `FraudFlag.status == "upheld"` before calling in. That's a real coupling risk worth naming honestly: a future caller that forgot to filter would silently over-penalize on unreviewed flags, and nothing in `compute_authenticity_score`'s type signature prevents that — it's enforced by convention and the one call site, not by the type system.

The relative weights encode a judgment call: `duplicate_profile` (40) is the heaviest penalty because it represents a structural attempt to game the platform itself (multiple accounts, likely to farm retries or violate a hackathon's one-entry rule) rather than a single dishonest claim. `code_plagiarism` (35) and `fake_certificate` (30) are close behind as direct, specific dishonesty about capability. `unrecognized_issuer` (10) is deliberately the second-smallest penalty, smaller than `fake_certificate`'s, because — as the code comment states plainly — this only means the issuer isn't in the trusted registry *yet*, not that a credential was positively confirmed forged; it's the weakest form of evidence in the whole system, appropriately priced. `components` in the returned dict lists exactly which flags contributed which penalty — a provenance trail so the number is never a black box, matching the same "show your work" pattern used elsewhere in the platform's scoring (e.g. Talent Score re-normalization).

These weights are explicitly called out in the code as tunable defaults, not validated against real outcome data — an honest limitation, not a hidden one.

## Key design decisions and why

- **Nodes are DB-free; the router does all persistence and gating.** Every detection tool/node takes plain data in `context` and returns signals/verdicts — no node ever queries or writes the database itself. This keeps detection logic pure and unit-testable in isolation, and it means the review-queue mechanics live in exactly one place (the router) instead of being re-implemented per subgraph.

- **Every signal is recorded, not just the ones that cross a flag threshold.** `verification_records` is a row-per-signal-per-check log, independent of whether a `FraudFlag` was created. This is the actual audit trail — an admin (or a future compliance review) can see exactly what was checked and what it found for any subject, including all the checks that came back clean. Without this, "clean" candidates would have no evidence they were checked at all.

- **LLM narrative is a layer on top of complete evidence, never a gate.** `report_llm.py`'s Fraud Risk Report and `dispute_review_llm.py`'s Dispute Review summary both explicitly fall back to deterministic behavior (a templated summary, or simply showing raw evidence with `dispute_review_assist.available=False`) if the LLM provider is unavailable. The flag and its evidence are constructed and persisted regardless of whether the narrative generation succeeds — a missing API key must never block or weaken an actual evidence-bearing flag.

- **The Dispute Review Agent is explicitly barred from recommending a verdict.** Its system prompt (`_GROUNDING_RULE` in `dispute_review_llm.py`) instructs it to neither state nor imply guilt, and its output schema has no field for a recommendation — only a neutral summary and a list of factual agreement/conflict points. This is a narrower, more defensible scope than "AI-assisted review" often implies in practice: the model is not deciding, or even nudging toward a decision, it's just compressing the candidate's statement against the evidence so the human reviewer reads faster.

## What could go wrong / current limitations

Being honest about this matters more here than anywhere else in the platform, because the cost of getting it wrong is a real person's opportunity.

- **False positives are not an edge case for several of these signals — they're structurally likely.** The AI-content heuristic is explicitly a statistical burstiness/lexical-diversity score, not a validated detector; the module's own docstring says false positives are "expected, especially for non-native-English writers and heavily-templated resume text." That it never auto-flags on its own is the mitigation, but a human reviewer combining it with a weak corroborating signal could still uphold a flag against someone who did nothing wrong except write in a formulaic, templated style.

- **MinHash/photo-hash duplicate detection can't distinguish malice from coincidence at the margins.** Two candidates who both used the same LinkedIn "About" template, or the same stock headshot vendor, could cross the similarity/Hamming thresholds without being the same person running two accounts. The default-avatar blacklist mitigates the photo case for the most common instance (literal platform placeholder images) but is hand-maintained and empty by default — it has to be populated in production as real default avatars are identified, and until it is, anyone who genuinely never uploaded a photo could theoretically collide with another such candidate.

- **A determined bad actor can still get through certificate verification.** Visual Forensics is explicitly a heuristic, not forensic-grade — it can be fooled by a well-made fake that has plausible layout/fonts/seal placement and complete (fabricated) metadata, since the rules-based check specifically rewards complete metadata with a lower suspicion score. A sufficiently careful forgery of a real, recognized issuer's certificate template, with a plausible-looking credential ID, could pass both the metadata rules check and a Haiku vision pass that has no ground-truth template to compare against.

- **The unrecognized-issuer signal is easy to defeat by choosing a well-known but currently-unregistered issuer, or hard to keep current by legitimate means.** Its accuracy is entirely a function of registry completeness, which is now human-maintained. That's a real improvement over the hardcoded dict, but it shifts the failure mode rather than eliminating it: an admin who's slow to add a legitimate new issuer generates false unrecognized-issuer signals against honest candidates citing that issuer, and conversely a candidate who cites a real but obscure issuer nobody has added yet gets the same (low, but nonzero) penalty treatment as someone citing a fabricated one.

- **GitHub cross-check has real availability limits.** Unauthenticated GitHub code search is rate-limited and explicitly documented as degrading to an inconclusive (not "clean") result on failure — but that means during periods of rate-limiting, this corroborating signal for plagiarism simply isn't available, and the plagiarism verdict falls back to relying on structural similarity alone.

- **The scoring weights are unvalidated defaults.** The penalty table in `aggregation.py` is explicitly documented as tunable, not derived from any real labeled dataset of confirmed-fraud outcomes. In a real deployment this would need calibration against actual review outcomes over time; right now it encodes a reasonable-sounding but unverified judgment call about relative severity.

- **The review queue itself is a bottleneck and a single point of human error.** Every safeguard in this module ultimately routes through one gate: a human reviewer's judgment on `PATCH /flags/{id}/review`. The system is only as fair as that reviewer's diligence — a reviewer who rubber-stamps "upheld" without genuinely weighing the evidence defeats the entire design, and nothing in the code can detect or prevent that; the `review_notes` requirement raises the bar for a lazy uphold but can't guarantee genuine consideration.

## Worked examples

A few concrete end-to-end traces through the verdict logic above, condensed:

| Scenario | Path | Result |
|---|---|---|
| AWS certificate, valid credential ID | `issuer_lookup` recognizes "AWS" → `auto_verify` GETs the issuer's verify URL → credential ID found on page | `verified=True`, `confirmed_genuine=True`, no flag; `unrecognized_issuer` check is suppressed |
| AWS certificate, fabricated credential ID | Same route to `auto_verify` → issuer's page returns 200 but the ID isn't present | `verified=False` → immediate `fake_certificate` flag, high-confidence evidence: "credential ID does not appear on issuer's verification page" |
| Certificate from an issuer not in the registry | `issuer_lookup` finds no match by name or alias → `visual_forensics` runs (rules + optional Haiku vision pass) → suspicion comes back "low" (metadata looks plausible) | Not flagged as fake, but `confirmed_genuine` stays `False` → `unrecognized_issuer` flag fires anyway (medium confidence) since nothing positively confirmed it |
| Two candidate accounts with the same profile photo | `photo_hash` computes perceptual hash (pHash) for both, Hamming distance ≤ 4/64 bits | `duplicate_profile` flag, evidence cites the exact bit distance; escalates to "high" confidence if the text fingerprint also matches |

Every one of these produces a `raised` flag (or no flag) — none of them touch
`AuthenticityScore` until a human reviewer explicitly upholds it with written notes, per the
core design principle above.

## Where this lives in the code

| Component | Path |
|---|---|
| Shared state schema | `services/agents/fraud/state.py` |
| Certificate verification graph | `services/agents/fraud/cert_graph.py` |
| Plagiarism graph | `services/agents/fraud/plagiarism_graph.py` |
| Duplicate profile graph | `services/agents/fraud/duplicate_graph.py` |
| AI-content graph | `services/agents/fraud/content_graph.py` |
| Issuer lookup (matching logic) | `services/agents/fraud/tools/issuer_lookup.py` |
| Issuer lookup node | `services/agents/fraud/nodes/issuer_lookup.py` |
| Certificate verdict (confirmed_genuine logic) | `services/agents/fraud/nodes/cert_verdict.py` |
| Auto-verify | `services/agents/fraud/tools/auto_verify.py` |
| Visual forensics | `services/agents/fraud/tools/visual_forensics.py` |
| Structural similarity (copydetect/AST-winnowing) | `services/agents/fraud/tools/structural_similarity.py` |
| Public repo cross-check | `services/agents/fraud/tools/github_crosscheck.py` |
| Plagiarism verdict | `services/agents/fraud/nodes/plagiarism_verdict.py` |
| Text fingerprint (MinHash/Jaccard) | `services/agents/fraud/tools/text_fingerprint.py` |
| Photo perceptual hash | `services/agents/fraud/tools/photo_hash.py` |
| Duplicate verdict | `services/agents/fraud/nodes/duplicate_verdict.py` |
| AI-content heuristic (shared with PPT Analyzer) | `services/agents/fraud/tools/perplexity_heuristic.py` |
| AI-content node | `services/agents/fraud/nodes/perplexity_heuristic.py` |
| Authenticity Score formula | `services/agents/fraud/tools/aggregation.py` |
| Fraud Risk Report (LLM narrative) | `services/agents/fraud/tools/report_llm.py` |
| Dispute Review Agent (assistive only) | `services/agents/fraud/tools/dispute_review_llm.py` |
| DB models (VerificationRecord, FraudFlag, AuthenticityScore, TrustedIssuer, Dispute) | `packages/db/models/fraud.py` |
| Trusted issuer registry table | `packages/db/migrations/versions/e8c387ea8123_baseline_schema.py` (squashed baseline) |
| Trusted issuer seed data | `scripts/seed_db.py` |
| API router (all endpoints) | `services/api/modules/fraud/router.py` |
| Admin fraud review queue UI | `apps/web/src/app/(admin)/fraud-review/page.tsx` |
| Admin flag audit/resolution UI | `apps/web/src/app/(admin)/fraud-review/[flagId]/page.tsx` |
| Admin trusted issuers UI | `apps/web/src/app/(admin)/trusted-issuers/page.tsx` |
| Candidate flags/dispute UI | `apps/web/src/app/(candidate)/my-flags/page.tsx` |
