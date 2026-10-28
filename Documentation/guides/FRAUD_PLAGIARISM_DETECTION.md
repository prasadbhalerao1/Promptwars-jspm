# Fraud & Plagiarism Detection System

**Updated:** 2026-08-01  
**Module:** FR-1 through FR-6 (Fraud Risk Framework)  
**Architecture:** LangGraph multi-signal verification pipeline  
**Design Principle:** "All flags are corroborated by independent signals, never a bare boolean"

---

## Overview

The system detects **6 fraud/integrity risks** with deterministic + AI signals:

1. **FR-1: Fake Credentials** — Certificate forgery (issuer verification)
2. **FR-2: Project Plagiarism** — Copied GitHub code
3. **FR-3: Resume Scam** — Fake portfolio/GitHub account
4. **FR-4: Duplicate Profile** — Same person, multiple accounts (resume text + photo)
5. **FR-5: Submission Plagiarism** — Copied hackathon/assessment code
6. **FR-6: Pitch Deck Plagiarism** — Reused slides from past submissions

**Core Pattern:** Every flag comes with:
- ✅ **Specific evidence** (what was detected)
- ✅ **Confidence level** (high/medium/low)
- ✅ **Multiple independent signals** (not a single heuristic)
- ✅ **Dispute mechanism** (humans can review/override)

---

## FR-1: Fake Credentials (Certificate Forgery)

### **Detection Flow**

```
Input: Candidate enters credential (e.g., "AWS Certified Solutions Architect")
         issuer="Amazon Web Services"
         credential_id="ABC-12345-XYZ"
                     ↓
    [Issuer Lookup] ──→ Is "AWS" in trusted_issuers registry?
                     ↓
                  YES → [Auto-Verify via URL]
                        Fetch: https://aws.amazon.com/verify?id=ABC-12345-XYZ
                        Status 200? Credential is REAL
                     ↓
                  NO → [Visual Forensics] ──→ Visual Forensics (below)
```

### **Trusted Issuer Registry**

Admin-managed database of legitimate issuers:

```python
TrustedIssuer(
  name="Amazon Web Services",
  aliases=["AWS"],
  verification_url_template="https://aw.amazon.com/verification?credential_id={credential_id}",
  trust_tier="high",  # "high", "medium", "low"
)
```

**Verification Methods:**
- ✅ **URL Verification** — Fetch issuer's verification page, check HTTP 200
- ❌ **Network Failure** → Treated as "inconclusive" (not flagged as fake)
- ❌ **Unrecognized Issuer** → Elevated risk, routes to Visual Forensics
- ❌ **No URL Template** → Known issuer, no automation path yet

### **Evidence Example**

```json
{
  "credential": "AWS Certified Solutions Architect",
  "verdict": {
    "is_verified": true,
    "is_recognized_issuer": true,
    "evidence": [
      "Issuer 'AWS' found in trusted registry (trust_tier: high)",
      "Fetched https://aws.amazon.com/verify?id=ABC-12345-XYZ -> HTTP 200"
    ]
  }
}
```

---

## FR-2: Project Plagiarism (GitHub Code)

### **Detection Methods**

**Method 1: Structural Similarity (Deterministic)**

Uses `copydetect` — AST-based token winnowing (Dolos algorithm):

```python
# Remove variable names, comments, whitespace
# Compare token sequences (robust to minor rewriting)

Candidate's code:
  def calculate_total(items):
    total = 0
    for item in items:
      total += item.price
    return total

Corpus code (by someone else):
  def sum_values(arr):
    result = 0
    for x in arr:
      result += x.value
    return result

Structural Similarity = 0.78/1.0  (HIGH → FLAG)
(Variable names differ, but logic is identical)
```

**Threshold:** `0.75` (configurable, documented in doc 08 §3)

**Output:**
```json
{
  "other_submission_id": "candidate-456",
  "similarity": 0.78,
  "evidence": "78.0% structural (AST-winnowing) token overlap with submission 456"
}
```

**Method 2: GitHub Public Repo Cross-Check**

Search GitHub for identical code snippets:

```python
# Extract 200-char distinctive snippet from candidate's code
snippet = "def download_and_cache(url, timeout=30):"

# Search GitHub
result = Github().search_code(f'"{snippet}"')

# If found in public repo NOT by candidate → plagiarism flag
if matches and not_candidate_owned:
  FLAG("GitHub plagiarism")
```

**Handles:**
- Rate limiting (gracefully degrades: "API unavailable, treat as inconclusive")
- Excludes candidate's own repos
- Top 5 matches returned

### **Evidence Example**

```json
{
  "structural_similarity": {
    "other_submission_id": "candidate-789",
    "similarity": 0.82,
    "evidence": "82.0% structural token overlap with submission 789"
  },
  "github_crosscheck": {
    "matches": [
      {
        "repo_full_name": "popular-ml-lib/algorithms",
        "html_url": "https://github.com/popular-ml-lib/algorithms/blob/main/sort.py"
      }
    ],
    "evidence": "Matching code snippet found in 1 public repo not authored by the candidate"
  }
}
```

---

## FR-4: Duplicate Profile (Same Person, Multiple Accounts)

### **Detection Signals**

**Signal 1: Text Fingerprinting (Resume/Profile Text)**

Uses `datasketch.MinHash` with Jaccard similarity:

```python
# Create 3-word shingles, hash them
Text A (Candidate 1):
  "5+ years Python backend engineer, built microservices at scale"
  Shingles: ["5 years python", "years python backend", "python backend engineer", ...]
  MinHash: [hash1, hash2, hash3, ...]

Text B (Candidate 2):
  "5+ years python backend engineer scaling microservices"
  Shingles: [similar, lots of overlap]
  MinHash: [hash1, hash2, hash3, ...]

Jaccard Similarity = 0.82  (HIGH → FLAG)
```

**Why MinHash?** Robust to minor rewording, detects near-duplicates (same person, lightly edited profile)

**Threshold:** `0.80` (tunable, documented)

**Signal 2: Photo Perceptual Hashing**

Uses `imagehash.phash()` (perceptual hash, not facial recognition):

```python
# Convert photo to grayscale, center-crop, DCT transform → 64-bit hash
Photo A: phash = "abc123def456..."
Photo B: phash = "abd123def456..."

# Hamming distance (how many bits differ out of 64)
Hamming Distance = 2 bits different  (EXACT MATCH → FLAG)
```

**Why perceptual hash (not facial recognition)?**
- ✅ Detects literal image reuse (same photo uploaded twice)
- ✅ Robust to minor compression/rotation
- ❌ Doesn't identify people (avoids GDPR/BIPA special-category data)
- ❌ Doesn't need face detection/alignment

**Threshold:** `≤ 4 bits` (tunable)

**Blacklist:** Stock avatar hashes (placeholder images that everyone has) → never flagged

### **Verdict Logic**

```python
text_match = text_similarity >= 0.80  # "80% text overlap"
photo_match = hamming_distance <= 4   # "≤4 bits different"

if text_match AND photo_match:
  confidence = "HIGH"    # Corroborated by 2 signals
elif text_match OR photo_match:
  confidence = "MEDIUM"  # Only 1 signal
else:
  confidence = "LOW"     # No signals
```

### **Evidence Example**

```json
{
  "verdict": {
    "flag_type": "duplicate_profile",
    "should_flag": true,
    "confidence_label": "high",
    "evidence": [
      "82.0% MinHash/Jaccard text overlap with candidate 123's profile",
      "Profile photo perceptual hash is 2 bits away (Hamming distance, 64-bit pHash) from candidate 123's photo"
    ]
  }
}
```

---

## FR-5: Submission Plagiarism (Hackathon/Assessment Code)

Same as **FR-2** (Project Plagiarism):
- ✅ Structural similarity via `copydetect` (AST winnowing)
- ✅ GitHub crosscheck (public repo search)
- ✅ Token-based, robust to variable renaming

Threshold: `0.75` structural similarity

---

## FR-6: Pitch Deck Plagiarism

### **Detection**

Embeds each slide's text as a vector, compares against past submissions via Qdrant:

```
Slide 1: "Problem: Lack of freelancer job matching in emerging markets"
         ↓
    [Embed slide text] → Vector [0.12, -0.45, ..., 0.89]
         ↓
    [Query Qdrant] → Compare to all past slide embeddings
         ↓
    Hit: "Similarity to past-hackathon-slide-42: 0.92"
         ↓
    0.92 >= 0.90 (threshold)? → FLAG
```

**Threshold:** `0.90` (high bar to reduce false positives on generic slides like "Problem Statement")

**Why high threshold?**
- "Problem Statement" (generic) slides will naturally be similar across decks
- 0.90 catches *real* plagiarism (nearly identical text)
- 0.90 not 0.75 because this is semantic similarity (looser) vs. AST winnowing (tighter)

### **Corpus Building**

Build as you go (no pre-existing corpus):
1. Check deck against existing submissions
2. Upsert this deck's slides into corpus
3. Next deck checked against updated corpus

**Evidence Example**

```json
{
  "plagiarism_flags": [
    {
      "matched_presentation_id": "past-hackathon-2024-05",
      "slide_index": 1,
      "similarity": 0.94,
      "evidence": "94.0% semantic similarity to slide 1 of past-hackathon-2024-05"
    }
  ]
}
```

---

## Architecture: LangGraph Verification Pipelines

### **Duplicate Profile Detection Pipeline**

```
START
  ↓
[text_fingerprint] ──→ MinHash/Jaccard analysis
  ↓
[photo_hash] ──→ Perceptual hash analysis
  ↓
[duplicate_verdict] ──→ Combine signals, set confidence
  ↓
END

Router pre-fetches:
- candidate's text + photo hash
- corpus of other candidates' text + photo hashes
```

### **Project Plagiarism Detection Pipeline**

```
START
  ↓
[structural_similarity] ──→ copydetect (AST winnowing)
  ↓
[github_crosscheck] ──→ GitHub code search
  ↓
[plagiarism_verdict] ──→ Combine signals
  ↓
[auto_verify] ──→ (Optional) Call Haiku for narrative
  ↓
END
```

### **Certificate Fraud Detection Pipeline**

```
START
  ↓
[issuer_lookup] ──→ Check trusted_issuers registry
                 ├─→ URL verification (HTTP GET)
                 └─→ Mark recognized vs. unrecognized
  ↓
[cert_verdict] ──→ Set flag + confidence
  ↓
[auto_verify] ──→ (Optional) Call Haiku for narrative
  ↓
END
```

---

## Thresholds & Tuning

| Signal | Threshold | Units | Tunable | Reasoning |
|--------|-----------|-------|---------|-----------|
| Text fingerprint (duplicate) | 0.80 | Jaccard 0-1 | ✅ Yes | 80% overlap = near-duplicate, lightly reworded |
| Photo hash (duplicate) | ≤ 4 | Hamming bits | ✅ Yes | Same person uploaded same photo to 2 accounts |
| Structural code (plagiarism) | 0.75 | Similarity 0-1 | ✅ Yes | AST winnowing, doc 08 §3 canonical |
| Pitch deck (plagiarism) | 0.90 | Cosine 0-1 | ✅ Yes | Higher than code (semantic, not AST) |

**Where documented:** Each threshold has a docstring citing why + which doc section. Tuned via A/B testing (future) or expert review, not magic numbers.

---

## Confidence Levels

```python
HIGH   = Corroborated by ≥2 independent signals
MEDIUM = Exactly 1 signal crosses threshold
LOW    = No signals, or all sub-threshold

Example:
  Text match (0.82) + Photo match (2 bits) → HIGH
  Text match (0.82) + Photo no match → MEDIUM
  Text no match + Photo no match → LOW
```

---

## Graceful Degradation

**Principle:** Unavailable signals never fabricate a result. Degrade transparently.

### **GitHub API Down**
```json
{
  "matches": [],
  "evidence": "GitHub code search unavailable (rate-limited): API error. Treat as inconclusive, not clean."
}
```

### **Qdrant Unavailable (Pitch Deck Check)**
```python
client = get_qdrant_client(raise_on_unavailable=False)
if client is None:
  return []  # No matches, report as inconclusive
```

### **Issuer Verification URL Unreachable**
```json
{
  "resolvable": false,
  "evidence": "Could not reach issuer verification page (https://...): Connection timeout. Treat as inconclusive."
}
```

**Never:** "Cannot reach service → assume it's fake" ❌  
**Always:** Report unavailability + treat as inconclusive

---

## Dispute & Appeal Mechanism

Every fraud flag is stored in `verification_records` table:

```python
VerificationRecord(
  candidate_id="...",
  check_type="duplicate_profile",
  result={
    "flag_type": "duplicate_profile",
    "should_flag": true,
    "confidence_label": "high",
    "evidence": [...]
  },
  status="flagged",  # or "disputed", "dismissed"
  dispute_evidence="I registered 2 accounts by mistake...",
  admin_review_notes="Checked manually, text is only 60% overlap, approved",
)
```

**Candidate can dispute** → Admin reviews → Override flag if warranted

---

## Security

### **Photo Hashing**

Perceptual hashing, not facial recognition (doc 06 §8):
- No GDPR special-category data
- Only detects image reuse, not identity

### **Resume Text**

- Text is personally identifiable
- Used for near-duplicate detection
- Stored in verification_records for audit trail

### **Code Repository Access**

GitHub code search is **public** (no token needed):
- Searches already-public code
- No private repos accessed
- Same as a human doing `site:github.com "search query"`

---

## Example: End-to-End Duplicate Profile Check

**Setup:**
```
Candidate A registers: "naveenbeniwal@gmail.com"
  Resume: "5+ years Python, FastAPI, React, PostgreSQL"
  Photo: [actual photo]

Candidate B registers: "naveen.beniwal@gmail.com"
  Resume: "5+ years in Python backend, built APIs with FastAPI"
  Photo: [same photo as A, compressed]
```

**Execution:**

1. **Text Fingerprint**
   ```
   A's shingles: ["5 years python", "python fastapi", ...]
   B's shingles: ["5 years python", "python backend", ...]
   Jaccard = 0.82  → MATCH
   ```

2. **Photo Hash**
   ```
   A's phash: "a1b2c3d4e5f6..."
   B's phash: "a1b2c3d4e5f7..."  (1 bit different due to compression)
   Hamming = 1  → MATCH (≤4)
   ```

3. **Verdict**
   ```
   Both signals match → confidence = "HIGH"
   Flag: "Duplicate profile detected"
   Evidence:
   - "82.0% MinHash/Jaccard text overlap with candidate B"
   - "Profile photo perceptual hash 1 bit away from candidate B"
   ```

4. **Action**
   ```
   Admin reviews: "Likely same person, 2 registrations"
   OR
   Candidate disputes: "Different email (I have 2), but same photo OK"
   Admin approves dispute
   ```

---

## Monitoring & Alerts

**Dashboard Metrics:**

```python
fraud_metrics = {
  "duplicate_profiles_flagged": 12,
  "duplicate_profiles_disputed": 3,
  "project_plagiarism_flagged": 5,
  "certs_unverified": 8,
  "high_confidence_flags": 10,
  "medium_confidence_flags": 5,
  "low_confidence_flags": 7,
}
```

**Alerts:**

- ✅ **High confidence + not disputed** → Review manually within 7 days
- ⚠️ **Pattern anomaly** → Sudden spike in plagiarism flags (possible attack?)
- 🔧 **Issuer API down** → 4+ consecutive verification failures

---

## References

- **doc 06 §4:** Fraud check framework & signals
- **doc 06 §7:** Evidence requirement ("every flag cites specific evidence")
- **doc 06 §8:** GDPR/BIPA constraints (perceptual hash, no facial recog)
- **doc 08 §3:** Code structural similarity threshold (0.75)
- **doc 08 §9:** Photo perceptual hash algorithm & blacklist
- **copydetect:** https://github.com/getdozer/copydetect (Dolos-style AST winnowing)
- **datasketch:** https://github.com/ekzhu/datasketch (MinHash, Jaccard)
- **imagehash:** https://github.com/JohannesBuchner/imagehash (perceptual hash)
