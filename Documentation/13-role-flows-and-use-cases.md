# Role Flows & Use Cases (Plain English)

---

## 1. Candidate — step-by-step flow

1. Sign up, select "I'm a candidate."
2. Land on an empty dashboard: *"Connect your evidence to get your Talent Score."*
3. Connect GitHub (one click, OAuth).
4. Upload a resume.
5. Optionally upload a LinkedIn data export and any certificates.
6. Dashboard shows "recalculating…" briefly, then the Talent Score appears with a full breakdown
   (Evidence Receipt) — not just a number.
7. If the system finds a conflict (e.g. resume says "5 years Python," GitHub shows 1 year of activity),
   candidate resolves it directly on the dashboard.
8. Candidate explores Career Guidance — skill gaps, a roadmap, a salary range.
9. Candidate generates a resume/portfolio, optionally tailored to a specific job.
10. Candidate applies to jobs, or gets discovered by a recruiter through search.
11. If a recruiter assigns an assessment, candidate takes it (code editor + MCQ, all in-browser).
12. If a recruiter schedules an AI interview, candidate does it by voice, in the browser, after
    a camera/mic check in the interview lobby.
13. Candidate can view any flags raised against their profile and submit a dispute with supporting
    evidence.
14. Candidate joins an in-platform hackathon, submits a project (repo + deck) directly.

### Candidate — use cases (plain English)
- I can connect my GitHub account and see my real coding activity summarized.
- I can upload my resume and have it turned into a structured profile automatically.
- I can import my own LinkedIn data without giving the platform my password or letting it scrape my profile.
- I can upload my certificates and see which ones the platform could actually verify.
- I can see exactly why I got the score I got — not just a number, but the evidence behind each part of it.
- I can see my score change over time as I do more.
- I can get badges for skills that show up in more than one place (like GitHub *and* a passed assessment).
- I can find out what skills I'm missing for a role I want, and a rough salary range for it.
- I can generate a clean resume and a public portfolio page without writing either from scratch.
- I can ask the platform to tailor my resume to a specific job without it inventing anything I haven't actually done.
- I can take a coding test and an MCQ test right in my browser.
- I can do an AI-run interview by voice, after I've clearly agreed to it.
- I can see if anyone has flagged something on my profile, and explain myself if they have.
- I can submit a hackathon project directly through the platform and have it count toward my profile.

---

## 2. Recruiter — step-by-step flow

1. Sign up as a recruiter, linked to their company.
2. Post a job (title, required skills, location, experience level).
3. See an auto-ranked list of matching candidates with a Match % and its breakdown.
4. Use the Copilot to search in plain language ("React developers with hackathon experience in Delhi").
5. Move candidates through pipeline stages on a kanban board.
6. Assign an assessment or schedule an AI interview for a candidate.
7. Review the resulting reports (technical rating, communication rating, hiring recommendation).
8. Check hiring analytics — funnel conversion, time-to-hire.
9. "Watch" a hackathon or skill area and get notified when a matching top performer appears.
10. If a candidate has a fraud flag, see that a flag exists (display-only) and decide accordingly — the
    platform never filters or auto-rejects for them.

### Recruiter — use cases (plain English)
- I can post a job and immediately see who's a strong match, ranked, with the reasoning shown.
- I can describe who I'm looking for in normal language instead of building a filter form.
- I can refine my search conversationally ("now only show ones open to remote").
- I can move candidates through my hiring pipeline on a simple board.
- I can send a candidate a coding test or an AI interview without leaving the platform.
- I can read a clear report after an interview — not a black-box pass/fail, an actual explanation.
- I can see how my hiring funnel is performing and where candidates drop off.
- I can get notified the moment a top hackathon performer matches something I'm hiring for.
- I can see if a candidate has an open trust concern, but I'm never shown a silently pre-filtered pool because of it — that decision stays mine.

---

## 3. Hackathon organizer — step-by-step flow

1. Create a hackathon event (name, dates, tracks).
2. Assign judges.
3. Teams register and submit directly through the platform (repo link + deck).
4. Judges score submissions against a rubric.
5. Platform automatically scores the linked repo and deck (reusing the assessment and PPT
   Analyzer modules) and combines it with judge scores into one ranking.
6. Rankings finalize — a public leaderboard goes live, and matching recruiters are notified of top
   performers.

### Organizer — use cases (plain English)
- I can set up a hackathon and have teams submit their projects directly, instead of chasing spreadsheets.
- I can assign judges and see their scores come in.
- I get an automatic ranking that combines judge scores with an AI read on code quality and pitch quality — not just judge opinion alone.
- I get a public leaderboard page I don't have to build myself.
- I know that once rankings are final, recruiters watching this event or this skill area get notified automatically — my event becomes an actual hiring pipeline, not a dead end.

---

## 4. Judge — step-by-step flow

1. Log in, see a queue of submissions assigned specifically to them.
2. Open a submission — repo, deck, and an AI-generated summary of it.
3. Score it against a fixed rubric.
4. Submit — it becomes part of that team's composite ranking.

### Judge — use cases (plain English)
- I only see the submissions assigned to me, not the whole event.
- I get a short AI summary of the project so I don't have to read a full deck cold before scoring it.
- I score against a consistent rubric, the same one every judge uses.

---

## 5. Admin — step-by-step flow

1. Log in, see the fraud review queue.
2. Open a flagged item, see the exact evidence behind it (matched certificate page, similarity score,
   flagged text).
3. Decide: uphold or dismiss, with a written reason either way.
4. Manage user roles across the platform.
5. Check the audit log for any action taken by any role.

### Admin — use cases (plain English)
- I see every fraud flag with the actual evidence, not just an accusation.
- I have to write a reason every time I uphold a flag — no silent adverse action.
- I can see a candidate's own dispute alongside the original evidence before deciding.
- I can manage who has which role on the platform.
- I can look back at what any user did, if something needs investigating later.

---

## 6. One thread that ties every role together

Every score, flag, or recommendation a candidate, recruiter, judge, or admin sees traces back to an
actual `agent_runs` record — the same Evidence Receipt component that appears on the candidate
dashboard is what the admin sees in the fraud review queue and what the recruiter sees in a match
breakdown. Nobody on this platform is ever shown a bare number they can't ask "why?" about.

See [09-trust-and-fraud-prevention.md](09-trust-and-fraud-prevention.md) and
[02-candidate-intelligence-and-talent-score.md](02-candidate-intelligence-and-talent-score.md)
for the mechanics behind that evidence trail.
