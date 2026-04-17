"""Named salience weights and retrieval utility coefficients.

These values used to live as magic numbers scattered across `runtime/loop.py`
and `memory/store._expected_utility`. They express relative importance
between memory kinds and between utility signals (lexical match, recency,
kind prior, verifier score). Keeping them here lets reviewers understand
why a retrieved working-memory note outranks (or loses to) an older
semantic fact without chasing the numbers through the code.

Nothing here is a first-principles optimum — they were hand-tuned against
the bench task set and then left stable once ablations looked sensible.
If you retune, bench the ablation suite before and after so the change is
measured, not merely felt.
"""
from __future__ import annotations


# --- Write-time salience ---------------------------------------------------

# Captured user input. High enough to stay visible during the run but not
# so high that multi-turn chatter drowns out retrieved facts.
USER_INPUT_SALIENCE = 0.64

# Successful tool observation — the model is likely to need the fresh
# result on the next step, so it should outrank generic retrieved memory.
TOOL_RESULT_OK_SALIENCE = 0.72

# Failed / errored tool observation. Still worth keeping (models often
# learn from the failure) but shouldn't outrank the ask itself.
TOOL_RESULT_ERROR_SALIENCE = 0.44

# Candidate answer written back at the end of a run before promotion.
# Lower than the user input because it's provisional — the verifier gate
# decides whether it's promoted to episodic/semantic.
FINAL_CANDIDATE_SALIENCE = 0.58

# Floor applied when promoting a verified answer to durable memory. Keeps
# promoted facts from being outranked by working-memory noise during
# retrieval, even if the verifier score itself was modest.
PROMOTED_FACT_SALIENCE_FLOOR = 0.7


# --- Retrieval utility coefficients ---------------------------------------
# `_expected_utility` mixes signals: lexical match against the query,
# stored salience, recency decay, a per-kind prior, and verifier score.
# Weights sum to ~0.92; the remaining headroom is absorbed by the kind
# bonus, which is added un-weighted. Retuning these should be paired with
# a bench run so the shift is visible.

UTILITY_LEXICAL_WEIGHT = 0.38
UTILITY_SALIENCE_WEIGHT = 0.32
UTILITY_RECENCY_WEIGHT = 0.14
UTILITY_VERIFIER_WEIGHT = 0.08

# Per-kind prior. Durable memory (semantic) is preferred when all else is
# equal because it survived the promotion gate; working memory is cheaper
# to disregard if the query shifts.
KIND_BONUS = {
    "working": 0.16,
    "episodic": 0.26,
    "semantic": 0.36,
    "style": 0.38,
    "experience": 0.40,
    "failure": 0.05,
}
KIND_BONUS_DEFAULT = 0.1
