"""One-shot developer calibration tool for the derived-road (下三路) vector
search. NOT part of the production seed/runtime flow.

Decides whether `describe_derived_in_nl`'s wording gives Voyage embeddings
enough separation to be useful for $vectorSearch, and if so, suggests a
value for DERIVED_PATTERN_MIN_SCORE.

IMPORTANT DESIGN NOTE: because a derived-road state is fully described by
just 3 roads x 2 colors, every possible state deterministically falls into
exactly one of the 5 archetypes this feature is built around (three-way
alignment, sustained dragon, alternating chop, majority complement,
extended-blue rebound) — there is no such thing as a truly "bogus / should
not match anything" road state the way there might be for an open-ended
NL pattern library. An earlier version of this script tried random
"should be ambiguous" queries and found they always legitimately matched
one of the 5 categories (as expected, by the pigeonhole argument above)
rather than exposing an actual embedding-quality problem.

Checks performed instead:
  1. Pairwise cosine similarity across all seeded derived patterns.
     - min / max / mean / median reported.
     - any pair > 0.90 -> flagged (the three "互補" variants are EXPECTED
       to score near 1.0 against each other since they're genuinely the
       same archetype differing only in which road is the odd one out,
       and they all predict the same next outcome — this is fine).
  2. Self-hit test: querying with each pattern's own canonical roads should
     return itself as top-1, with a healthy top1-top2 gap.
  3. Realistic-scenario recall test: for each of the 5 archetypes, build a
     longer (12-symbol), cleanly-isolated, realistic-looking tail that
     should NOT trivially also satisfy a higher-priority archetype, and
     verify it top-1 matches the corresponding seeded pattern. The score
     here (rarely 1.0, since the tail differs from the toy canonical
     example) is a much more honest estimate of real production scores
     than the trivial self-hit test.
  4. Suggested threshold = min(realistic-scenario top-1 scores) - a small
     margin, bounded to [0.5, 0.95], and sanity-checked against the
     cross-archetype pairwise ceiling (excluding the 互補 trio) so the
     threshold sits strictly above typical cross-category noise.

Usage:
    python -m app.seed.calibrate_derived
"""

from __future__ import annotations

import asyncio
import itertools
import logging

import numpy as np

from app.db import close_client, get_db
from app.seed.default_derived_patterns import DEFAULT_DERIVED_PATTERNS
from app.services.derived_roads import DerivedTailSymbols, describe_derived_in_nl
from app.services.embedder import embed_text

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# One realistic, cleanly-isolated 12-symbol scenario per archetype, each
# constructed so it does NOT accidentally also satisfy a higher-priority
# archetype (see describe_derived_in_nl's priority order: alignment ->
# rebound -> dragon -> chop -> complement).
REALISTIC_SCENARIOS: list[tuple[str, DerivedTailSymbols]] = [
    (
        "三元及第",
        DerivedTailSymbols(bigEye="RBRBRBRBRBRR", small="BRBRBRBRBRRR", cockroach="RBRBRBRBRBRR"),
    ),
    (
        "下三路連龍",
        DerivedTailSymbols(bigEye="RRRRRRRRRRRR", small="BRBRBRBRBRBR", cockroach="RBRBRBRBRBRB"),
    ),
    (
        "下三路單跳",
        DerivedTailSymbols(bigEye="RBRBRBRBRBRB", small="RRBBRRBBRRBB", cockroach="BBRRBBRRBBRR"),
    ),
    (
        "三路互補-蟑螂藍",
        DerivedTailSymbols(bigEye="RBRBBRBRRBBR", small="BRBBRRBBRBBR", cockroach="RRBBRBBRBRBB"),
    ),
    (
        "逢藍知返",
        DerivedTailSymbols(bigEye="RBRBRBBBB", small="BRBRBRBRBR", cockroach="RBRBRBRBRB"),
    ),
]


def _cosine(a: list[float], b: list[float]) -> float:
    va, vb = np.array(a), np.array(b)
    return float(np.dot(va, vb) / (np.linalg.norm(va) * np.linalg.norm(vb)))


async def main() -> None:
    print("=" * 70)
    print("Derived-road (下三路) vector search calibration")
    print("=" * 70)

    names = [p["name"] for p in DEFAULT_DERIVED_PATTERNS]
    texts = [describe_derived_in_nl(DerivedTailSymbols(**p["canonicalRoads"])) for p in DEFAULT_DERIVED_PATTERNS]

    print(f"\nEmbedding {len(texts)} seeded derived patterns (document mode)...")
    vectors = []
    for t in texts:
        vectors.append(await embed_text(t, mode="document"))

    # 1. Pairwise cosine matrix. Pairs where BOTH patterns are 互補 variants
    # are expected to score near 1.0 (same archetype, same prediction,
    # different odd-road-out) and are excluded from the "too tight overall"
    # warning, but still printed for visibility.
    print("\n--- 1. Pairwise cosine similarity across seeded patterns ---")
    complement_names = {n for n in names if n.startswith("三路互補")}
    pairs = list(itertools.combinations(range(len(vectors)), 2))
    sims = []
    cross_archetype_sims = []
    for i, j in pairs:
        sim = _cosine(vectors[i], vectors[j])
        sims.append(sim)
        both_complement = names[i] in complement_names and names[j] in complement_names
        if not both_complement:
            cross_archetype_sims.append(sim)
        flag = ""
        if sim > 0.90 and not both_complement:
            flag = " ⚠️  TOO SIMILAR"
        elif both_complement:
            flag = " (expected: same archetype, different odd-road-out)"
        print(f"  {names[i]:16s} vs {names[j]:16s}: {sim:.4f}{flag}")

    sims_arr = np.array(sims)
    cross_arr = np.array(cross_archetype_sims)
    print(
        f"\n  all-pairs:        min={sims_arr.min():.4f} max={sims_arr.max():.4f} mean={sims_arr.mean():.4f}"
    )
    print(
        f"  cross-archetype:  min={cross_arr.min():.4f} max={cross_arr.max():.4f} mean={cross_arr.mean():.4f} "
        f"(excludes 互補-vs-互補 pairs)"
    )
    if cross_arr.max() > 0.90:
        print("  ⚠️  WARNING: cross-archetype similarity > 0.90 — some distinct categories may collide.")

    # 2. Self-hit test. A small top1-top2 gap is expected (and fine) when
    # top2 is a sibling 互補 variant, since those genuinely share the same
    # archetype and the same predicted outcome.
    print("\n--- 2. Self-hit test (query with own canonical roads) ---")
    self_hit_ok = True
    for i, (name, vec) in enumerate(zip(names, vectors)):
        scored = sorted(
            ((names[j], _cosine(vec, vectors[j])) for j in range(len(vectors))),
            key=lambda x: -x[1],
        )
        top1_name, top1_score = scored[0]
        top2_name, top2_score = scored[1] if len(scored) > 1 else (None, 0.0)
        gap = top1_score - top2_score
        gap_acceptable = gap >= 0.02 or (name in complement_names and top2_name in complement_names)
        ok = top1_name == name and gap_acceptable
        self_hit_ok = self_hit_ok and ok
        note = " (sibling 互補 tie, OK)" if gap < 0.02 and name in complement_names else ""
        flag = "✓" if ok else "✗"
        print(f"  {flag} {name:16s} top1={top1_name} ({top1_score:.4f}) gap={gap:.4f}{note}")

    if not self_hit_ok:
        print("  ⚠️  WARNING: some patterns don't cleanly self-match with a healthy gap.")

    # 3. Realistic-scenario recall test
    print("\n--- 3. Realistic-scenario recall test (longer, cleanly-isolated tails) ---")
    realistic_top1_scores = []
    recall_ok = True
    for expected_name, scenario in REALISTIC_SCENARIOS:
        text = describe_derived_in_nl(scenario)
        qvec = await embed_text(text, mode="query")
        scored = sorted(((names[j], _cosine(qvec, vectors[j])) for j in range(len(vectors))), key=lambda x: -x[1])
        top1_name, top1_score = scored[0]
        top2_score = scored[1][1] if len(scored) > 1 else 0.0
        gap = top1_score - top2_score
        correct = top1_name == expected_name
        recall_ok = recall_ok and correct
        realistic_top1_scores.append(top1_score)
        flag = "✓" if correct else f"✗ (expected {expected_name})"
        print(f"  {flag} scenario-for-{expected_name:14s} -> top1={top1_name} ({top1_score:.4f}) gap={gap:.4f}")

    if not recall_ok:
        print("  ⚠️  WARNING: at least one realistic scenario did not recall its intended archetype.")

    # 4. Suggested threshold: comfortably below the weakest genuine match,
    # but strictly above the cross-archetype noise ceiling from check #1.
    floor = min(realistic_top1_scores) - 0.05
    ceiling = cross_arr.max() + 0.02
    suggested = min(0.95, max(0.5, max(floor, ceiling)))
    print("\n--- 4. Suggested DERIVED_PATTERN_MIN_SCORE ---")
    print(f"  min(realistic recall top1 scores) = {min(realistic_top1_scores):.4f}")
    print(f"  cross-archetype noise ceiling     = {cross_arr.max():.4f}")
    print(f"  suggested threshold               = {suggested:.4f}")
    print(f"\n  -> Set DERIVED_PATTERN_MIN_SCORE={suggested:.2f} in .env, or")
    print(f"     derived_pattern_min_score: float = {suggested:.2f} in app/config.py")

    overall_pass = cross_arr.max() <= 0.85 and self_hit_ok and recall_ok
    print("\n" + "=" * 70)
    if overall_pass:
        print("CALIBRATION PASSED — describe_derived_in_nl gives Voyage enough separation to use.")
    else:
        print("CALIBRATION NEEDS ATTENTION — consider further rewriting describe_derived_in_nl")
        print("before finalizing DERIVED_PATTERN_MIN_SCORE.")
    print("=" * 70)

    await close_client()


if __name__ == "__main__":
    asyncio.run(main())
