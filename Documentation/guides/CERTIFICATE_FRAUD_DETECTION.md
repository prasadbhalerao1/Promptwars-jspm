# Certificate Fraud Detection (FR-1) — Deep Dive

**Updated:** 2026-08-01  
**Module:** FR-1 (Fake Credentials)  
**Architecture:** LangGraph-based certificate verification pipeline  
**Design Principle:** "Conservative by design — only flag what we can prove, never guess"

---

## Overview

When a candidate claims a credential (e.g., "AWS Certified Solutions Architect"), the system verifies it via **two independent paths**:

```
Candidate: "AWS Certified Solutions Architect, ID: ABC-12345"
                     ↓
         [Issuer Lookup]
                     ↓
    ┌─────────────────┴─────────────────┐
    ↓                                   ↓
[URL Found]                      [No URL Found]
    ↓                                   ↓
[Auto-Verify]              [Visual Forensics]
(Fast, certain)            (Haiku vision, fuzzy)
    ↓                                   ↓
    └─────────────────┬─────────────────┘
                      ↓
              [Cert Verdict]
                      ↓
            Flag or Approve
```

---

## Step 1: Issuer Lookup

### **Purpose**
Determine if the issuer (e.g., "AWS", "Google", "Coursera") is in the **Trusted Issuer Registry** and has a verification URL.

### **Trusted Issuer Registry**

Admin-maintained database of legitimate credential issuers:

```python
TrustedIssuer {
  name: "Amazon Web Services",
  aliases: ["AWS", "Amazon Web Services"],
  verification_url_template: "https://aw.amazon.com/verification?credential_id={credential_id}",
  trust_tier: "high",  # high, medium, low
}

TrustedIssuer {
  name: "Coursera",
  aliases: ["Coursera Inc."],
  verification_url_template: "https://coursera.org/verify/{credential_id}",
  trust_tier: "high",
}

TrustedIssuer {
  name: "LinkedIn Learning",
  aliases: ["LinkedIn"],
  verification_url_template: null,  # Known issuer, no auto-verify URL yet
  trust_tier: "medium",
}
```

### **Lookup Logic**

**Case-insensitive substring matching:**

```python
def resolve_issuer(issuer: str, trusted_issuers: list[dict]) -> tuple[dict | None, bool]:
    """
    Returns: (matched_issuer_row_or_None, is_recognized)
    """
    key = issuer.strip().lower()  # "amazon web services"
    
    for row in trusted_issuers:
        candidates = [row["name"], *(row.get("aliases") or [])]
        # "AWS" in "amazon web services" OR "amazon web services" in "AWS"?
        if any(name.lower() in key or key in name.lower() for name in candidates):
            return row, True
    
    return None, False
```

**Examples:**

| Input | Matches | Recognized |
|-------|---------|-----------|
| "Amazon Web Services (AWS)" | AWS row | YES |
| "AWS" | AWS row | YES |
| "aws" | AWS row | YES |
| "XYZ Institute" | None | NO ❌ |
| "Google Cloud" | GCP row | YES |

### **Output**

```json
{
  "is_recognized_issuer": true,
  "verification_url_template": "https://aw.amazon.com/verification?credential_id={credential_id}",
  "resolvable": true  // URL is available
}
```

OR (if unrecognized):

```json
{
  "is_recognized_issuer": false,
  "verification_url_template": null,
  "resolvable": false,
  "evidence": "Issuer 'XYZ Institute' is not in the trusted issuer registry"
}
```

---

## Step 2A: Auto-Verify (When Issuer has URL)

### **Purpose**
Fetch the issuer's verification page and confirm the credential ID appears on it.

### **Flow**

```
Input: issuer="AWS", credential_id="ABC-12345"
       verification_url_template="https://aw.amazon.com/verification?credential_id={credential_id}"
                     ↓
       1. Substitute: URL = "https://aw.amazon.com/verification?credential_id=ABC-12345"
                     ↓
       2. HTTP GET the URL → response
                     ↓
       3. Check HTTP status
            200? Continue
            404? Credential doesn't exist → FAKE
            503? Issuer down → INCONCLUSIVE
                     ↓
       4. If 200: Search response text for "ABC-12345"
            Found? → VERIFIED ✅
            Not found? → FAKE ❌
```

### **Implementation**

```python
def auto_verify(credential_id: str, page_text_sample: str, http_status: int) -> dict:
    """
    Returns: {verified: bool|None, confidence_label, evidence}
    
    verified = True:  Credential found on issuer page
    verified = False: Page loaded (200) but credential not found
    verified = None:  Page didn't load (4xx/5xx)
    """
    
    if http_status != 200:
        return {
            "verified": None,  # Don't guess
            "confidence_label": "low",
            "evidence": f"Issuer page returned HTTP {http_status}"
        }
    
    if credential_id and credential_id in page_text_sample:
        return {
            "verified": True,  # CONFIRMED REAL
            "confidence_label": "high",
            "evidence": f"Credential ID '{credential_id}' found on issuer's page"
        }
    
    return {
        "verified": False,  # CONFIRMED FAKE
        "confidence_label": "medium",
        "evidence": f"Page loaded but credential ID '{credential_id}' not found"
    }
```

### **Example: AWS Certificate**

**Scenario 1: Real certificate**
```
Candidate: "AWS Certified Solutions Architect, ID: 1A2B3C4D"

Lookup: AWS → verification_url = "https://aw.amazon.com/verification?credential_id=1A2B3C4D"
GET https://aw.amazon.com/verification?credential_id=1A2B3C4D
Response: 200 OK
Page content: "AWS Certification Verified ✓ 1A2B3C4D issued to John Doe"

Contains "1A2B3C4D"? YES
Result: VERIFIED = TRUE ✅
Confidence: HIGH
```

**Scenario 2: Fake certificate**
```
Candidate: "AWS Certified Solutions Architect, ID: FAKE-FAKE-FAKE"

GET https://aw.amazon.com/verification?credential_id=FAKE-FAKE-FAKE
Response: 200 OK
Page content: "No credentials found for ID: FAKE-FAKE-FAKE"

Contains "FAKE-FAKE-FAKE"? NO
Result: VERIFIED = FALSE ❌
Confidence: MEDIUM (page loaded, but credential doesn't exist)
```

**Scenario 3: Issuer down**
```
Candidate: "AWS Certified Solutions Architect, ID: 1A2B3C4D"

GET https://aw.amazon.com/verification?...
Response: 503 Service Unavailable

Result: VERIFIED = NONE (inconclusive)
Confidence: LOW (can't verify right now)
Action: Try again later, don't flag yet
```

---

## Step 2B: Visual Forensics (When No URL Available)

### **Purpose**
When the issuer has no auto-verify URL (e.g., "Local Training Institute"), use visual inspection + Haiku to assess if the certificate looks real.

### **Two-Layer Approach**

**Layer 1: Rules-Based (Always Works)**

Check certificate metadata for red flags:

```python
def _rules_based_suspicion(
    issuer: str | None,
    title: str | None,
    credential_id: str | None,
    ocr_confidence: float | None
) -> dict:
    """
    Returns: {suspicion_label: "low"|"medium"|"high", reasons: [str]}
    """
    suspicion_points = 0
    reasons = []
    
    # Check 1: Issuer present
    if not issuer:
        reasons.append("No issuer name extracted")
        suspicion_points += 1  # +1 point
    
    # Check 2: Certificate title present
    if not title:
        reasons.append("No certificate title extracted")
        suspicion_points += 1  # +1 point
    
    # Check 3: Credential ID present (critical for verification)
    if not credential_id:
        reasons.append("No credential ID — cannot cross-check")
        suspicion_points += 1  # +1 point
    
    # Check 4: OCR quality (if certificate scanned)
    if ocr_confidence is not None and ocr_confidence < 0.55:
        reasons.append(f"Low OCR confidence: {ocr_confidence:.2f}")
        suspicion_points += 1  # +1 point
    
    # Map points to suspicion level
    if suspicion_points >= 3:
        label = "high"      # 3+ red flags = probably fake
    elif suspicion_points >= 1:
        label = "medium"    # 1-2 red flags = suspicious
    else:
        label = "low"       # 0 red flags = looks OK
    
    return {"suspicion_label": label, "reasons": reasons}
```

**Suspicion Scoring:**

| Points | Label | Meaning |
|--------|-------|---------|
| 0 | LOW | All fields present, OCR confident |
| 1-2 | MEDIUM | Some fields missing or OCR weak |
| 3+ | HIGH | Multiple missing fields = likely fake |

**Example:**

```
Candidate uploads: "certificate.jpg" (scanned image)
  Issuer: "XYZ Training Institute"
  Title: "Python Developer Certification"
  Credential ID: "CERT-2024-001"
  OCR Confidence: 0.92

Check results:
  ✅ Issuer present
  ✅ Title present
  ✅ Credential ID present
  ✅ OCR high confidence

Points: 0 → SUSPICION = LOW
```

**Example (Fake Certificate):**

```
Candidate uploads: "certificate.jpg"
  Issuer: [empty]
  Title: [empty]
  Credential ID: [empty]
  OCR Confidence: 0.30

Check results:
  ❌ No issuer
  ❌ No title
  ❌ No credential ID
  ❌ OCR very low

Points: 4 → SUSPICION = HIGH (obvious fake)
```

---

**Layer 2: Haiku Vision Pass (Optional Enhancement)**

If certificate image is available (`public_url`), call Haiku for visual assessment:

```python
async def _vision_pass(
    public_url: str,
    issuer: str,
    title: str
) -> dict | None:
    """
    Optional Haiku vision call to assess layout/design plausibility
    Returns: {suspicion_label, rationale} or None if unavailable
    """
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=400,
        tools=[{
            "name": "visual_forensics_verdict",
            "input_schema": {
                "type": "object",
                "properties": {
                    "suspicion_label": {
                        "type": "string",
                        "enum": ["low", "medium", "high"]
                    },
                    "rationale": {"type": "string"}
                }
            }
        }],
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": f"Certificate claiming '{issuer}' for '{title}'. Assess layout, fonts, seal plausibility. Never claim certainty — output only low/medium/high suspicion."
                },
                {
                    "type": "image",
                    "source": {"type": "url", "url": public_url}
                }
            ]
        }]
    )
    # Extract tool output
    return response.content[0].input  # {suspicion_label, rationale}
```

**What Haiku Looks For:**

- ✅ **Layout consistency** — Balanced, professional arrangement
- ✅ **Font consistency** — Matching typefaces, sizes
- ✅ **Seal/signature area** — Looks like real certificate template
- ✅ **Paper texture** — Not obviously digital-only

**What Haiku CANNOT Do:**

- ❌ Verify issuer's exact template (no ground truth)
- ❌ Confirm issuer actually issued it (only URL verification does that)
- ❌ Claim certainty (only "low/medium/high suspicion")

**Why Optional?** If `public_url` is missing or API key not configured, still use rules-based suspicion alone. Never fail due to missing optional signal.

### **Final Suspicion Level**

Combine rules + vision (if available):

```python
def assess_visual_forensics(
    issuer: str,
    title: str,
    credential_id: str,
    ocr_confidence: float,
    public_url: str
) -> dict:
    
    rules = _rules_based_suspicion(issuer, title, credential_id, ocr_confidence)
    vision = _vision_pass(public_url, issuer, title) if public_url else None
    
    if vision is not None:
        # Pick the HIGHER of the two suspicions (conservative)
        # DON'T average or downweight one
        order = {"low": 0, "medium": 1, "high": 2}
        final_label = max(
            rules["suspicion_label"],
            vision["suspicion_label"],
            key=lambda l: order[l]
        )
        evidence = rules["reasons"] + [f"Haiku: {vision['rationale']}"]
        confidence = "medium"  # Rules + vision = decent confidence
    else:
        # Rules only (no vision pass)
        final_label = rules["suspicion_label"]
        evidence = rules["reasons"]
        confidence = "low"  # Metadata-only, lower confidence
    
    return {
        "suspicion_label": final_label,
        "confidence_label": confidence,
        "evidence": evidence
    }
```

**Example:**

```
Rules: "low" (all fields present)
Vision: "medium" (fonts look weird)

Final: max("low", "medium") = "medium"
Confidence: "medium"
Evidence: ["All fields present", "Haiku: Fonts look inconsistent"]
```

---

## Step 3: Cert Verdict (Decision Engine)

### **Decision Tree**

```
IF auto_verify.verified == False (confirmed fake):
    RESULT: FLAG as fake (HIGH confidence)

ELSE IF auto_verify.verified == True (confirmed real):
    RESULT: PASS (HIGH confidence)
    NOTE: Suppress unrecognized_issuer flag (already proven genuine)

ELSE IF auto_verify.verified == None (inconclusive):
    IF visual_forensics.suspicion == "high":
        RESULT: FLAG as suspicious (MEDIUM confidence)
    ELSE:
        RESULT: PASS (but lower confidence)
        IF issuer is not recognized:
            RESULT: FLAG as unrecognized_issuer (MEDIUM confidence)
            NOTE: Separate flag type, requires human review

ELSE (no checks ran):
    IF issuer is not recognized:
        RESULT: FLAG as unrecognized_issuer (MEDIUM confidence)
    ELSE:
        RESULT: PASS (LOW confidence)
```

### **Implementation**

```python
async def run(state: FraudCheckState) -> dict:
    ctx = state["context"]
    auto_verify_result = ctx.get("auto_verify_result")
    visual_result = ctx.get("visual_forensics_result")
    issuer_lookup_result = ctx.get("issuer_lookup_result")
    
    # Flag 1: Auto-Verify says it's FAKE
    if auto_verify_result is not None:
        if auto_verify_result["verified"] is False:
            return {
                "verdict": {
                    "flag_type": "fake_certificate",
                    "should_flag": True,
                    "confidence_label": "medium",  # Not 100% certain
                    "evidence": [auto_verify_result["evidence"]]
                }
            }
        # Auto-Verify says it's REAL
        confirmed_genuine = True
        # ... pass with high confidence
    
    # Flag 2: Visual Forensics says it's HIGHLY suspicious
    elif visual_result is not None:
        if visual_result["suspicion_label"] == "high":
            return {
                "verdict": {
                    "flag_type": "fake_certificate",
                    "should_flag": True,
                    "confidence_label": visual_result["confidence_label"],
                    "evidence": visual_result["evidence"]
                }
            }
        # Visual says medium/low — not flagged
        confirmed_genuine = False
    
    # Flag 3: Issuer is not recognized (weaker signal)
    if (
        not confirmed_genuine
        and issuer_lookup_result is not None
        and issuer_lookup_result.get("is_recognized_issuer") is False
    ):
        return {
            "verdict": {
                "flag_type": "unrecognized_issuer",
                "should_flag": True,
                "confidence_label": "medium",
                "evidence": [
                    issuer_lookup_result["evidence"],
                    "No stronger verification signals confirmed this is genuine"
                ]
            }
        }
    
    # Default: Pass (no red flags)
    return {
        "verdict": {
            "flag_type": "fake_certificate",
            "should_flag": False,
            "confidence_label": "low",
            "evidence": ["No verification concerns detected"]
        }
    }
```

### **Flag Types**

**Type 1: `fake_certificate` (High Confidence)**
- Triggered when: Auto-verify says credential doesn't exist OR visual forensics says "high suspicion"
- Confidence: HIGH or MEDIUM
- Action: Human review required before rejection

**Type 2: `unrecognized_issuer` (Medium Confidence)**
- Triggered when: Issuer not in registry AND no other check confirmed genuineness
- Confidence: MEDIUM
- Action: Human review, may add issuer to registry if legitimate

---

## Example Flows

### **Example 1: AWS Credential (Happy Path)**

```
Input:
  issuer: "AWS"
  title: "Solutions Architect Associate"
  credential_id: "ABC-12345"

Step 1: Issuer Lookup
  ✅ "AWS" found in registry
  ✅ verification_url: "https://aw.amazon.com/verify?id=ABC-12345"
  → ROUTE: auto_verify

Step 2A: Auto-Verify
  ✅ GET https://aw.amazon.com/verify?id=ABC-12345 → 200 OK
  ✅ Response contains "ABC-12345"
  → verified = True
  → confidence = HIGH

Step 3: Cert Verdict
  IF verified == True:
    RESULT: should_flag = False (PASS)
    Suppress any unrecognized_issuer flag
  
FINAL: ✅ CREDENTIAL VERIFIED
```

### **Example 2: Fake AWS Credential**

```
Input:
  issuer: "AWS"
  title: "Solutions Architect Associate"
  credential_id: "FAKE-FAKE-FAKE"

Step 1: Issuer Lookup
  ✅ "AWS" found in registry
  ✅ verification_url available
  → ROUTE: auto_verify

Step 2A: Auto-Verify
  ✅ GET https://aw.amazon.com/verify?id=FAKE-FAKE-FAKE → 200 OK
  ❌ Response: "No credentials found for this ID"
  → verified = False
  → confidence = MEDIUM

Step 3: Cert Verdict
  IF verified == False:
    RESULT: should_flag = True (FLAG as FAKE)
  
FINAL: ❌ CREDENTIAL FLAGGED AS FAKE
Evidence: "Credential ID 'FAKE-FAKE-FAKE' does not appear on issuer's verification page"
```

### **Example 3: Unknown Issuer (No URL)**

```
Input:
  issuer: "XYZ Training Institute"
  title: "Advanced Python"
  credential_id: "CERT-2024-001"
  public_url: "cert.jpg" (scanned certificate)

Step 1: Issuer Lookup
  ❌ "XYZ Training Institute" NOT in registry
  ❌ No verification_url
  → is_recognized_issuer = False
  → ROUTE: visual_forensics

Step 2B: Visual Forensics
  Rules:
    ✅ Issuer present
    ✅ Title present
    ✅ Credential ID present
    ✅ OCR confidence 0.85
    → suspicion_label = "low"
  
  Vision (Haiku):
    "Layout looks reasonable, fonts consistent, seal area plausible"
    → suspicion_label = "low"
  
  Final: max("low", "low") = "low"
  confidence = "medium"

Step 3: Cert Verdict
  IF visual.suspicion != "high":
    should_flag = False (initially)
  
  IF issuer not recognized AND verified != True:
    RESULT: should_flag = True
    flag_type = "unrecognized_issuer"
  
FINAL: ⚠️ FLAGGED AS UNRECOGNIZED_ISSUER
Evidence:
  - "XYZ Training Institute is not in the trusted issuer registry"
  - "No auto-verification path available"
  - "Metadata and visual assessment look plausible, but human review recommended"
```

### **Example 4: Obvious Fake Certificate**

```
Input:
  issuer: [empty - OCR failed]
  title: [empty - OCR failed]
  credential_id: [empty]
  ocr_confidence: 0.20
  public_url: "obviously_fake.jpg"

Step 2B: Visual Forensics
  Rules:
    ❌ No issuer → +1
    ❌ No title → +1
    ❌ No credential ID → +1
    ❌ OCR too low (0.20) → +1
    → suspicion_points = 4
    → suspicion_label = "high"
  
  Vision (Haiku):
    "This looks like a generic image, not a real certificate"
    → suspicion_label = "high"
  
  Final: max("high", "high") = "high"

Step 3: Cert Verdict
  IF visual.suspicion == "high":
    RESULT: should_flag = True
    flag_type = "fake_certificate"
  
FINAL: ❌ FLAGGED AS FAKE
Confidence: MEDIUM (visual-only, not auto-verified)
Evidence:
  - "No issuer name extracted from certificate"
  - "No certificate title extracted"
  - "No credential ID present"
  - "Low OCR extraction confidence (0.20)"
  - "Haiku: This looks like a generic image, not a real certificate"
```

---

## Confidence Levels Explained

| Level | Auto-Verify | Visual | Meaning |
|-------|-------------|--------|---------|
| HIGH | URL found + 200 + ID matches | — | Issuer's own page confirms it |
| MEDIUM | URL found but 404 OR Visual "high" suspicion + rules | Haiku + rules | Fairly certain but not issuer-confirmed |
| LOW | No URL available, rules only | Rules only | Metadata-based assessment only |

---

## Security Considerations

### **Rate Limiting**
```python
# Avoid hitting issuer APIs too hard
# - 1 request per credential per day (cache results)
# - Retry after 503 with exponential backoff
```

### **Network Timeouts**
```python
# Issuer verification URLs must respond within 6 seconds
# If timeout → treated as INCONCLUSIVE (not fake)
async with httpx.AsyncClient(timeout=6.0) as client:
    response = await client.get(verification_url)
```

### **False Positives**
```python
# Error on the side of caution
# - Medium confidence for visual-only checks
# - HIGH confidence only when issuer's own page confirms
# - Unrecognized issuer ≠ fake (just needs review)
```

---

## Admin Tasks

### **Adding a New Issuer**

```python
# Admin adds row to trusted_issuers table
INSERT INTO trusted_issuers (
  name,
  aliases,
  verification_url_template,
  trust_tier,
  created_by
) VALUES (
  'Coursera',
  '["Coursera Inc.", "Coursera Online"]',
  'https://coursera.org/verify/{credential_id}',
  'high',
  'admin@trace-platform.ai'
);
```

### **Updating Verification URL**

```python
UPDATE trusted_issuers
SET verification_url_template = 'https://new-url.com/verify/{credential_id}'
WHERE name = 'AWS';

# Old credentials already verified? Leave them alone (cached in verification_records)
# New credentials? Use new URL
```

### **Disputing a Flagged Certificate**

```python
# Candidate claims flag is wrong
UPDATE verification_records
SET status = 'disputed',
    dispute_evidence = 'I can provide letter from issuer'
WHERE id = '...';

# Admin reviews
UPDATE verification_records
SET status = 'dismissed',
    admin_review_notes = 'Confirmed with issuer directly'
WHERE id = '...';
```

---

## Monitoring

**Key Metrics:**

```python
fraud_metrics = {
  "certs_verified_auto": 1200,      # Auto-verify succeeded
  "certs_failed_auto": 45,          # Credential ID not found
  "certs_unverified_no_url": 320,   # Visual-forensics-only
  "certs_flagged_fake": 12,         # Flagged as fake
  "certs_flagged_unrecognized": 28, # Unrecognized issuer
  "high_confidence_flags": 8,
  "medium_confidence_flags": 32,
  "disputes_filed": 3,
  "disputes_approved": 2,
}
```

**Alerts:**

- ⚠️ Issuer API returns 503 consistently → escalate to admin
- 📊 Sudden spike in "unrecognized_issuer" flags → possible new issuer wave
- 🚨 Same issuer, 10+ fake flags in one day → possible attack pattern

---

## References

- **doc 06 §4:** Certificate verification architecture
- **doc 06 §8:** GDPR/BIPA constraints (no facial recognition)
- **services/agents/fraud/cert_graph.py:** LangGraph pipeline
- **services/agents/fraud/tools/issuer_lookup.py:** Registry lookup
- **services/agents/fraud/tools/auto_verify.py:** URL-based verification
- **services/agents/fraud/tools/visual_forensics.py:** Haiku vision + rules
- **services/agents/fraud/nodes/cert_verdict.py:** Decision logic
