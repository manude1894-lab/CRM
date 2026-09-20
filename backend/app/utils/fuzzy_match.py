"""Lightweight fuzzy name matching for duplicate-detection warnings.

Stdlib difflib only — no new dependency. Built for the current data volumes
(hundreds, not hundreds of thousands, of Accounts/Prospects), not a search index.
"""
import re
from difflib import SequenceMatcher

_PUNCT_RE = re.compile(r"[^\w\s]")
_SUFFIX_RE = re.compile(
    r"\b(llc|ltd|limited|inc|incorporated|corp|corporation|llp|plc|fzco|fze|fzc|co)\b",
    re.IGNORECASE,
)


def normalize(name: str) -> str:
    s = _PUNCT_RE.sub(" ", name or "")
    s = _SUFFIX_RE.sub(" ", s)
    return " ".join(s.lower().split())


def top_matches(
    name: str, candidates: list[tuple[int, str]], limit: int = 5, threshold: float = 0.6,
) -> list[tuple[int, str, int]]:
    """candidates: list of (id, name). Returns (id, name, score 0-100), sorted desc, score >= threshold*100."""
    target = normalize(name)
    if not target:
        return []
    scored = []
    for cid, cname in candidates:
        cand_norm = normalize(cname)
        if not cand_norm:
            continue
        ratio = SequenceMatcher(None, target, cand_norm).ratio()
        if ratio >= threshold:
            scored.append((cid, cname, round(ratio * 100)))
    scored.sort(key=lambda t: t[2], reverse=True)
    return scored[:limit]
