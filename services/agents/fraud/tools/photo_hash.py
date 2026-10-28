"""Photo Perceptual-Hash Agent — doc 06 §4/§8, doc 08 §9's exact algorithm. FR-4.

Deliberately perceptual hashing (`imagehash`), NOT facial recognition — detects literal
image reuse, not biometric identity, which is what keeps this outside BIPA/GDPR
special-category-data territory (doc 06 §8, binding constraint). Plain center-crop only,
no face-detection/alignment step (doc 08 §9's explicit correction from an earlier draft
that added one).

This module has no DB access and relies on the router for any gating, per the
"nodes/tools stay DB-free, router enforces gates" convention used throughout.
"""

import io

import imagehash
from PIL import Image
from services.api.core.config import get_settings

# Doc 08 §9 step 5: tunable default, Hamming distance <= 4 (out of 64 bits) flags a
# duplicate photo.
HAMMING_DISTANCE_FLAG_THRESHOLD = get_settings().photo_hash_distance_threshold

# Hand-maintained blacklist of hashes for common default/stock avatars (e.g. a platform's
# own placeholder image) — doc 08 §9 step 3: "compare against a blacklist first, to avoid
# flagging everyone who never uploaded a real photo."
#
# Now stored in the `default_avatar_hashes` table rather than here: the instruction this
# comment used to carry — "populate with real default-avatar hashes as they're
# identified in production" — is impossible to follow for a code literal, since every
# addition would need a developer and a deploy at exactly the moment an admin has
# spotted a new placeholder avatar in live data.
#
# Kept as an empty set for backwards compatibility with any direct importer; read
# through `_blacklist()` instead, which resolves from the database.
DEFAULT_AVATAR_HASH_BLACKLIST: set[str] = set()


def _blacklist() -> set[str]:
    """Known placeholder-avatar hashes, from the database (empty if none recorded)."""
    from services.agents.catalogs import default_avatar_hashes

    return default_avatar_hashes() | DEFAULT_AVATAR_HASH_BLACKLIST


def compute_photo_hash(image_bytes: bytes) -> str | None:
    """Plain center-crop to 8x8 grayscale, DCT pHash -> 64-bit hash, per doc 08 §9 steps
    1-2. Returns None (not an error) for anything that isn't a decodable image."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img = img.convert("L")  # grayscale

        # Plain center-crop to a square before hashing (doc 08 §9 step 1 — no
        # face-alignment, just a symmetric crop to the shorter side).
        width, height = img.size
        side = min(width, height)
        left = (width - side) // 2
        top = (height - side) // 2
        img = img.crop((left, top, left + side, top + side))

        return str(imagehash.phash(img))
    except Exception:
        return None


def hamming_distance(hash_a: str, hash_b: str) -> int:
    return imagehash.hex_to_hash(hash_a) - imagehash.hex_to_hash(hash_b)


def find_duplicate_photos(target_hash: str, corpus: list[tuple[str, str]]) -> list[dict]:
    """`corpus` is [(other_candidate_id, other_hash), ...]. Skips anything matching the
    blacklist first (doc 08 §9 step 3) so default avatars never generate false positives.
    Returns [{other_candidate_id, hamming_distance, evidence}] for every non-blacklisted
    comparison, sorted by distance ascending (closest match first)."""
    blacklist = _blacklist()
    if target_hash in blacklist:
        return []

    results: list[dict] = []
    for other_id, other_hash in corpus:
        if not other_hash or other_hash in blacklist:
            continue
        distance = hamming_distance(target_hash, other_hash)
        results.append(
            {
                "other_candidate_id": other_id,
                "hamming_distance": distance,
                "evidence": (
                    f"Profile photo perceptual hash is {distance} bits away (Hamming distance, "
                    f"64-bit pHash) from candidate {other_id}'s profile photo."
                ),
            }
        )
    return sorted(results, key=lambda r: r["hamming_distance"])
