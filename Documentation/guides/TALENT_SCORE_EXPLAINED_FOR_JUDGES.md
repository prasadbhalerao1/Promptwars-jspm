# Talent Score: How We Rate Candidates

## What is Talent Score?

**Talent Score** is a 0-100 rating of a candidate's technical ability, work quality, and community impact. It's computed automatically from:
- GitHub data (code quality, commit history, projects)
- Problem-solving assessments (coding challenges)
- Hackathon performance
- Open-source contributions

Think of it like a "developer credit score" — but tailored for the specific job you're hiring for.

---

## The Nine Dimensions We Measure

### 1. **Coding Ability** (16% of overall score)
**What it measures:** Raw programming skill and code quality.

**How we calculate it:**
- Count commits across their own repos (log-scaled so 200 commits ≈ 80/100)
- Analyze code complexity (sample their Python files, measure cyclomatic complexity)
  - Simple, readable code (CC ≤ 5) = 100
  - Moderately complex (CC 5-15) = 70-100
  - Overly complex (CC > 15) = 0-70
- Their assessment score (latest coding challenge percentile)

**Example:** Jane has 150 commits, low-complexity code, and scored 82nd percentile on assessments → Coding Ability = 78

---

### 2. **Problem Solving** (16% of overall score)
**What it measures:** Ability to solve algorithmic challenges and tricky problems.

**How we calculate it:**
- Their latest score on problem-solving assessments (LeetCode-style coding challenges)
- Percentile-ranked against all other candidates

**Example:** Jane scored 1450/2000 on assessment → 73rd percentile vs peers → Problem Solving = 73

---

### 3. **Project Quality** (12% of overall score)
**What it measures:** Polish, documentation, and maintainability of their projects.

**How we calculate it:**
- **Mechanical:** Cyclomatic complexity analysis (same as coding_ability)
- **LLM Review:** Claude AI reads their README files and repo descriptions, rates architecture and documentation quality 0-100
- Blend: 60% complexity score + 40% LLM judgment (if both available)

**Example:** Jane's code is clean (CC=6, score 84) and her READMEs are thorough (LLM score 82) → Project Quality = 83

---

### 4. **Innovation** (12% of overall score)
**What it measures:** How novel and unique their projects are (not just clones of tutorials).

**How we calculate it:**
- Embed descriptions of their top 5 projects into a vector space
- Compare against embeddings of all other candidate projects in our database
- Score based on semantic uniqueness (how different from the crowd)
- Apply recency decay (newer projects score higher than abandoned ones)

**Example:** Jane built a novel ML pipeline for time-series forecasting → high uniqueness score → Innovation = 81

---

### 5. **Technical Consistency** (8% of overall score)
**What it measures:** Do they code regularly or in sporadic bursts?

**How we calculate it:**
- Analyze their 52-week GitHub commit activity
- Calculate coefficient of variation (measures regularity)
- Penalize long inactivity gaps
- Bonus for sustained cadence

**Example:** Jane commits almost every week with no 2+ week gaps → Technical Consistency = 87

---

### 6. **Community Participation** (8% of overall score)
**What it measures:** How many people find their work useful (stars) and how much they help others (external PRs).

**How we calculate it:**
- **Star score:** Total stars across all repos, percentile-normalized vs candidate pool (60% weight)
- **Contribution score:** External merged PRs (5 PRs = 40 points max) (40% weight)

**Example:** Jane's repos have 450 stars (90th percentile) and 3 merged external PRs → Community = 72

---

### 7. **Leadership** (8% of overall score)
**What it measures:** Do they mentor others and maintain projects?

**How we calculate it:**
- Owned/maintained repos (each = +10, capped at 50)
- PR reviews they've done on others' code (each = +5, capped at 50)
- Percentile-ranked vs candidate pool

**Example:** Jane maintains 3 repos and reviewed 8 PRs → raw score 50, percentile-ranked → Leadership = 74

---

### 8. **Open Source Contributions** (10% of overall score)
**What it measures:** How active in the open-source community are they?

**How we calculate it:**
- Count merged PRs to projects they don't own
- Bonus for diversity (spread across many projects, not just one)
- Percentile-ranked vs pool

**Example:** Jane has 6 merged PRs across 4 different projects → Open Source = 68

---

### 9. **Hackathon Performance** (10% of overall score)
**What it measures:** Track record in time-pressured competitions.

**How we calculate it:**
- **Verified:** Results from hackathons run on our platform (wins/top5/finalist/participant)
- **Self-reported:** External hackathons they list (lower weight than verified)
- Weight by performance tier (wins > top5 > finalist > participant)

**Example:** Jane won 1 platform hackathon, top5 in 2 others → Hackathon Performance = 79

---

## Overall Score: The Weighted Average

We combine all 9 dimensions:

```
Overall = (0.16 × Coding Ability)
        + (0.16 × Problem Solving)
        + (0.12 × Project Quality)
        + (0.12 × Innovation)
        + (0.08 × Technical Consistency)
        + (0.08 × Community Participation)
        + (0.08 × Leadership)
        + (0.10 × Open Source)
        + (0.10 × Hackathon Performance)
```

**Cold-start handling:** If a candidate is missing some dimensions (e.g., no hackathon history), those weights redistribute. We never penalize incomplete profiles.

**Example with Jane's scores:**
```
(0.16 × 78) + (0.16 × 73) + (0.12 × 83) + (0.12 × 81)
+ (0.08 × 87) + (0.08 × 72) + (0.08 × 74) + (0.10 × 68) + (0.10 × 79)
= 12.5 + 11.7 + 10.0 + 9.7 + 7.0 + 5.8 + 5.9 + 6.8 + 7.9
= 77.3 → Overall Score = 77
```

Jane's overall Talent Score is **77/100**.

---

## Job-Contextual Adjustment

But here's the catch: **Jane's score changes depending on the job.**

A score of 77 means nothing without context. Jane might be great for a backend Python role but weak for a frontend React role.

### How We Adjust for Specific Jobs

When matching Jane to a job, we:

1. **Check skill overlap:** What fraction of the job's required skills does Jane have?
   - If job needs: Python, SQL, Docker
   - Jane has: Python (verified), PostgreSQL (embedding-similar to SQL), no Docker
   - Skill overlap ratio = 1.0 + 0.54 + 0.0 = 1.54 / 3 = **0.51** (51% match)

2. **Adjust technical sub-scores:**
   ```
   coding_ability_adjusted = 78 × 0.51 = 39.8
   problem_solving_adjusted = 73 × 0.51 = 37.2
   project_quality_adjusted = 83 × (0.51 × 0.8) = 33.8
   innovation_adjusted = 81 × (0.51 × 0.8) = 32.8
   ```

3. **Keep universal traits unchanged:**
   ```
   leadership = 74 (unchanged)
   community = 72 (unchanged)
   ```

4. **Recompute overall:**
   ```
   Adjusted = weighted_mean([39.8, 37.2, 33.8, 32.8, 87, 72, 74, 68, 79])
            ≈ 51/100
   ```

**Jane's score for this backend job: 51/100** (down from 77).

Why? Because she only has 51% of the required skills. Her leadership and community participation are valuable anywhere, but her coding ability for *this specific tech stack* is only 51% relevant.

---

## Why This Matters for Judges

### As a Judge, You See:

**Profile Page (Candidate's General Talent):**
- Overall Score: **77/100**
- Breakdown of all 9 dimensions
- Evidence for each (GitHub links, assessment scores, hackathon wins)

**Job Matching (Candidate for a Specific Role):**
- Job-Specific Score: **51/100**
- Skill overlap ratio: **51%**
- Adjustment factor: **0.66x** (from 77 to 51)
- Which sub-scores were adjusted and why

### When to Trust the Score

✅ **High confidence when:**
- Candidate has multiple data signals (GitHub + assessments + hackathons)
- Skill overlap is high (> 75%)
- Profile is recent (not stale GitHub data from 2 years ago)

⚠️ **Lower confidence when:**
- Candidate is new (cold-start: few GitHub repos, no assessments yet)
- Skill overlap is low (< 30%) — score might be misleading
- Job requirements are vague or missing skills list

---

## FAQ for Judges

**Q: Why does Jane's score drop from 77 to 51?**
A: Because the job needs specific skills (Python, SQL, Docker) and she's missing 49% of them. Her general talent is high, but her fit for *this* job is medium.

**Q: Can a candidate with a 51 score still be good?**
A: Yes! They might learn the missing skills quickly if their problem-solving (73) and coding ability (40 adjusted) are strong. The score is one signal, not a veto.

**Q: What if the job didn't list required skills?**
A: We use the generic score (77). You can't do job-specific adjustment without a skill list.

**Q: Why do leadership and community scores not adjust?**
A: Because they're universal — a good leader or community contributor is valuable everywhere, not just for jobs requiring Python.

**Q: What about assessments? Can candidates game those?**
A: Hard to game — they're live coding challenges (LeetCode-style). Lucky guessing fails on the percentile because everyone takes the same test.

**Q: Why percentile-rank instead of absolute scores?**
A: Because "7 GitHub stars" means different things depending on the candidate pool. If everyone has 5 stars, 7 is great. If everyone has 500, 7 is weak. Percentile handles that.

---

## Technical Notes (For Curious Judges)

- **Encoding:** All scores are normalized to 0-100 and stored in the TalentScore table with timestamps
- **Refresh:** Scores auto-update weekly when candidates refresh their GitHub data
- **Validation:** We check for data availability before scoring; missing data doesn't create fake scores (returns `None`, not 0)
- **Embedding model:** SentenceTransformer for skill similarity and project novelty scoring
- **LLM component:** Claude AI for project quality judgment and innovation assessment

---

## Summary

**Talent Score = Multidimensional measure of developer capability**
- 9 sub-scores (coding, problem-solving, quality, innovation, consistency, community, leadership, open-source, hackathon)
- Weighted average (no dimension dominates)
- Cold-start safe (missing data doesn't break scoring)
- Job-contextual (same candidate, different scores for different jobs based on skill fit)

**Use it to:**
- Quickly identify strong candidates (high score + recent data)
- Understand skill gaps (see which dimensions are weak)
- Compare fit across jobs (job-specific score tells you relevance)

**Don't use it to:**
- Reject candidates outright based on score alone
- Compare scores across different jobs (always use job-specific version)
- Override your domain expertise (score is data-driven, you are domain-expert)
