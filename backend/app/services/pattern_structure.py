"""Structural classification of B/P run-shapes, used as a deterministic
pre-filter for pattern matching that replaced an earlier `minWindowLen`
(raw length) guard.

Why this exists (see conversation/design doc for full history): pure
embedding similarity on describe_window_in_nl() text can rank a pattern
whose narrative literally has not happened yet above one that actually did,
purely from incidental token overlap (e.g. "ongoing Banker streak of 4"
appears in both a plain 4-round "BBBB" window and the tail description of a
9-round "break-then-resume" pattern). A hard length cutoff (`minWindowLen`)
fixed the worst cases but was too rigid: it also excluded a pattern from
matching mid-narrative (e.g. a 7-round window that is genuinely in the
middle of re-enacting a 9-round "break-then-resume" story, just not finished
yet) and required business users defining custom patterns to get exact run
lengths right.

This module replaces the raw-length guard with a *categorical* structural
check: classify both patterns and live windows into coarse narrative shapes
(continuous run / long-run-broken-then-resumed / long-run-broken-and-over /
all-short-runs-chopping / uncategorized-complex) using *relative* thresholds
(what counts as "long" vs "short"), not pattern-specific exact numbers. A
window is only eligible to match a pattern if the window's run history is
still a *plausible, not-yet-falsified* instance of that pattern's category.
Fine-grained ranking among structurally-eligible candidates is still left
entirely to vector-search cosine similarity.
"""

from __future__ import annotations

from app.services.window_text import compute_runs

# Relative thresholds defining "long" vs "short" runs for classification
# purposes. These are intentionally coarse category boundaries, not exact
# numbers copied from any one pattern's canonicalSequence, so that e.g. a
# [(B,3),(P,2),(B,2)] window is recognized as the same narrative family as a
# [(B,4),(P,1),(B,4)] pattern ("莊龍回頭") without requiring exact length
# equality.
MAIN_RUN_MIN = 3
INTERRUPT_MAX = 2

CONTINUOUS_RUN = "continuous_run"
BREAK_RESUME = "break_resume"
BREAK_END = "break_end"
CHOP = "chop"
COMPLEX = "complex"

ALL_CATEGORIES = (CONTINUOUS_RUN, BREAK_RESUME, BREAK_END, CHOP, COMPLEX)


def _bp_runs(sequence: list[str]) -> list[tuple[str, int]]:
    """Run-decompose a sequence, dropping Tie runs. Ties don't participate
    in the B/P narrative shapes we classify here; patterns that meaningfully
    depend on Tie placement (e.g. "和局夾擊") fall through to COMPLEX below,
    which is the safe/conservative fallback (pure embedding ranking, no
    structural filtering)."""
    return [r for r in compute_runs(sequence) if r[0] in ("B", "P")]


def classify_structure(sequence: list[str]) -> str:
    """Classify a *complete* sequence (a pattern's canonicalSequence) into
    one of the coarse narrative categories above. Used once at pattern
    create/update time to derive the stored `structuralCategory` field."""
    runs = _bp_runs(sequence)

    if len(runs) == 0:
        return COMPLEX
    if len(runs) == 1:
        return CONTINUOUS_RUN
    if len(runs) == 2:
        main_sym, main_len = runs[0]
        _, _ = runs[1]
        if main_len >= MAIN_RUN_MIN:
            return BREAK_END
        if all(length <= INTERRUPT_MAX for _, length in runs):
            return CHOP
        return COMPLEX
    if len(runs) == 3:
        (a_sym, a_len), (b_sym, b_len), (c_sym, c_len) = runs
        if a_sym == c_sym and b_sym != a_sym and a_len >= MAIN_RUN_MIN and b_len <= INTERRUPT_MAX:
            return BREAK_RESUME
        if all(length <= INTERRUPT_MAX for _, length in runs):
            return CHOP
        return COMPLEX
    # 4+ runs: only a genuine chop-like shape (every run short) is
    # classifiable with confidence; anything else is COMPLEX and falls back
    # to pure embedding ranking.
    if all(length <= INTERRUPT_MAX for _, length in runs):
        return CHOP
    return COMPLEX


def compatible_categories(sequence: list[str]) -> set[str]:
    """Given the *live, still-unfolding* window, return the set of
    structural categories it remains a plausible (not-yet-falsified)
    instance of. COMPLEX is always included so that patterns which couldn't
    be confidently classified (see classify_structure) are never
    structurally excluded — they fall back to pure embedding ranking, same
    as the pre-existing behavior before this filter existed.

    The logic walks the window's run decomposition and only rules out a
    category once the window's actual shape contradicts it; anything not
    yet contradicted stays "live". This is deliberately permissive for
    early/ambiguous windows (e.g. a plain 4-round "BBBB" window remains
    compatible with both CONTINUOUS_RUN and BREAK_RESUME, since nothing has
    happened yet to rule either out — this is a genuine, acceptable
    ambiguity, not a bug) and becomes strict once the window's own history
    rules something out (e.g. once a window shows 3 runs, BREAK_END -
    which only ever has exactly 2 runs - is permanently excluded).
    """
    runs = _bp_runs(sequence)
    live: set[str] = {COMPLEX}

    if len(runs) == 0:
        # No B/P rounds at all yet (e.g. window is all Ties so far) -
        # nothing can be ruled out.
        live |= {CONTINUOUS_RUN, BREAK_RESUME, BREAK_END, CHOP}
        return live

    first_len = runs[0][1]

    if len(runs) == 1:
        live.add(CONTINUOUS_RUN)
        # CHOP requires every run to stay short; still possible as long as
        # the current (only) run hasn't already exceeded the short-run cap.
        if first_len <= INTERRUPT_MAX:
            live.add(CHOP)
        # BREAK_RESUME / BREAK_END both need the first run to eventually
        # become "long"; not yet falsified regardless of current length
        # (it could still grow).
        live.add(BREAK_RESUME)
        live.add(BREAK_END)
        return live

    # len(runs) >= 2: a side-switch has happened, so a single
    # window-spanning CONTINUOUS_RUN narrative is no longer literally true.
    if all(length <= INTERRUPT_MAX for _, length in runs):
        live.add(CHOP)

    # However, if the *current* (most recent, still potentially growing) run
    # has itself grown long enough, it's also reasonable to read the window
    # as "a fresh long dragon is happening right now" - regardless of what
    # happened earlier (e.g. "BBBBPBBB": the resumed B run is itself a
    # 3-run streak). Re-admit CONTINUOUS_RUN based on the tail run alone, so
    # it can compete/tie with BREAK_RESUME via normal vector-search scoring
    # instead of being permanently ruled out the moment any interruption
    # occurred anywhere earlier in the window.
    if runs[-1][1] >= MAIN_RUN_MIN:
        live.add(CONTINUOUS_RUN)

    if first_len >= MAIN_RUN_MIN and runs[1][1] <= INTERRUPT_MAX:
        if len(runs) == 2:
            # Exactly "long run, then switch" so far - still a live
            # candidate for BREAK_END (which requires precisely 2 runs) and
            # for BREAK_RESUME (a 3rd same-side run could still appear).
            live.add(BREAK_END)
            live.add(BREAK_RESUME)
        elif len(runs) == 3 and runs[2][0] == runs[0][0]:
            # Resumed on the same side as the original main run - exactly
            # the BREAK_RESUME shape, still in progress or just completed.
            live.add(BREAK_RESUME)
        # len(runs) >= 3 with a 3rd run on the *other* side, or len(runs) > 3
        # at all, means both BREAK_END (too many runs) and BREAK_RESUME
        # (shape violated) are falsified - nothing added beyond COMPLEX/CHOP.

    return live
