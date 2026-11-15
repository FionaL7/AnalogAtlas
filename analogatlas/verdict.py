"""The report card's bottom line (#50): a transfer-confidence tier.

Not "likelihood of replicating": the Earth's-limits rows on every card say
nothing on Earth replicates the lunar or Martian surface. The tier answers a
narrower question — how much of what is tested at this Earth site transfers
to the target — and is derived from the card itself, so it can be checked
against the rows above it.

Rule: over the comparable rows (kind == "compare" with a match value), the
share that hold (match >= HOLDS). STRONG at or above 0.7, MODERATE at or
above 0.4, PARTIAL below. The optional LLM prose (#51) only narrates this
block; it never produces the tier.
"""
from __future__ import annotations

import math
from typing import Iterable

import pandas as pd

HOLDS = 0.6     # a row "holds" (same bar as fieldtest.HOLDS and the UI)
STRONG = 0.7    # tier bars on the holding share
MODERATE = 0.4
TOP_N = 2       # dimensions named per side

RULE = ("Share of comparable report-card rows with match >= 0.6: "
        "strong >= 0.7, moderate >= 0.4, partial below. "
        "Earth's-limits rows always break and stay out of the share.")


def _match(row: dict) -> float | None:
    m = row.get("match")
    if m is None:
        return None
    try:
        m = float(m)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(m) else m


def tier_of(holds_frac: float) -> str:
    if holds_frac >= STRONG:
        return "strong"
    if holds_frac >= MODERATE:
        return "moderate"
    return "partial"


def _sentence(tier: str, held: list[dict], broke: list[dict], n: int,
              field_tests: dict | None) -> str:
    bits = [f"{tier.capitalize()} analog: {len(held)} of {n} comparable dimensions hold"]
    if held:
        names = " and ".join(r["dimension"] for r in held[:TOP_N])
        bits[0] += f", led by {names}"
    if broke:
        names = " and ".join(r["dimension"] for r in broke[:TOP_N])
        bits.append(f"{names} break{'s' if len(broke[:TOP_N]) == 1 else ''} down")
    else:
        bits.append("no comparable dimension breaks down")
    text = "; ".join(bits) + "."
    tests = (field_tests or {}).get("tests") or []
    if tests:
        text += f" Best suited to {tests[0]['title'].lower()}."
    return text


def verdict(rows: Iterable[dict] | pd.DataFrame,
            field_tests: dict | None = None) -> dict | None:
    """The verdict block for one report card, or None when the card has no
    comparable rows to judge (e.g. an export without climate)."""
    if isinstance(rows, pd.DataFrame):
        rows = rows.to_dict("records")
    comp = [dict(r, match=_match(r)) for r in rows
            if r.get("kind", "compare") == "compare" and _match(r) is not None]
    if not comp:
        return None
    held = sorted((r for r in comp if r["match"] >= HOLDS), key=lambda r: -r["match"])
    broke = sorted((r for r in comp if r["match"] < HOLDS), key=lambda r: r["match"])
    holds_frac = len(held) / len(comp)
    tier = tier_of(holds_frac)
    return dict(
        tier=tier,
        holds_frac=round(holds_frac, 4),
        n_compare=len(comp),
        top_holds=[r["dimension"] for r in held[:TOP_N]],
        top_breaks=[r["dimension"] for r in broke[:TOP_N]],
        sentence=_sentence(tier, held, broke, len(comp), field_tests),
    )
