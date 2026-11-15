"""Step 7: LLM prose for the verdict blocks (#51).

    python scripts/07_verdicts.py              # fill missing prose, patch twins
    python scripts/07_verdicts.py --limit 3    # a trial run on 3 cards
    python scripts/07_verdicts.py --force      # regenerate everything
    python scripts/07_verdicts.py --show artemis-i__E12345   # print the prompt, no call

The LLM never produces the tier, a score or a fact: it narrates the verdict
block and report card that scripts/03_export.py computed (#50). It runs
offline, once, so the demo path stays static and judging never waits on an
LLM. Every paragraph must be read by a human against its card before
`data.py push`; the script prints each one for that purpose.

Provider-agnostic: plain OpenAI-compatible `chat/completions` over HTTP
(requests, no SDK). Configure in `.env`:

    LLM_BASE_URL   e.g. https://generativelanguage.googleapis.com/v1beta/openai
                   (Gemini's OpenAI-compatible endpoint, free tier), or any
                   other provider speaking the same API
    LLM_API_KEY
    LLM_MODEL      e.g. gemini-2.5-flash

Reads the exported cards in web/public/data/twins/, writes the cache
data/index/verdicts.json (reruns only fill gaps) and patches each twin's
`verdict.prose` in place. scripts/03_export.py merges the cache too, so a
later export keeps the prose.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analogatlas import config as C  # noqa: E402  (loads .env)

CACHE = C.INDEX / "verdicts.json"
TWINS = C.ROOT / "web" / "public" / "data" / "twins"
WORD_LIMIT = 100
TIMEOUT_S = 60
RETRIES = 3

SYSTEM = (
    "You write the bottom-line summary on a planetary-analog report card: how well "
    "field tests at an Earth site transfer to a site on the {body}. Use ONLY the data "
    "provided; never invent numbers, place names or facts. One paragraph, at most "
    f"{WORD_LIMIT} words, plain prose, no headings or lists. Cover: the overall tier in the "
    "first sentence; the strongest matching dimensions with their values; where the "
    "analogy breaks down (including one limit no Earth site can reproduce); and what is "
    "worth testing here. Do not soften the breaks."
)


def card_payload(card: dict) -> dict:
    """The subset of a twin card the model may use: the verdict block, every
    report-card row, and the rule-derived field tests."""
    return dict(
        verdict={k: v for k, v in card["verdict"].items() if k != "prose"},
        rows=[dict(dimension=r["dimension"], target=r["moon"], earth=r["earth"],
                   match=r["match"], kind=r["kind"], note=r["note"])
              for r in card["breakdown"]],
        field_tests=dict(
            tests=[dict(title=t["title"], risk=t["risk"]) for t in card["field_tests"]["tests"]],
            avoid=[a["reason"] for a in card["field_tests"]["avoid"]],
        ),
    )


def prompt_for(card: dict) -> list[dict]:
    body = "Mars" if card["moon"].get("body") == "mars" else "Moon"
    return [dict(role="system", content=SYSTEM.format(body=body)),
            dict(role="user", content=json.dumps(card_payload(card), indent=1))]


def complete(messages: list[dict], base_url: str, api_key: str, model: str) -> str:
    url = base_url.rstrip("/") + "/chat/completions"
    for attempt in range(RETRIES):
        r = requests.post(url, timeout=TIMEOUT_S,
                          headers={"Authorization": f"Bearer {api_key}"},
                          json=dict(model=model, messages=messages,
                                    temperature=0, max_tokens=400))
        if r.status_code == 429 or r.status_code >= 500:
            wait = float(r.headers.get("Retry-After", 15 * (attempt + 1)))
            print(f"  {r.status_code}, retrying in {wait:.0f}s")
            time.sleep(wait)
            continue
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    r.raise_for_status()
    raise RuntimeError("unreachable")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, help="generate at most this many (trial run)")
    ap.add_argument("--force", action="store_true", help="regenerate cached prose too")
    ap.add_argument("--show", metavar="KEY", help="print the prompt for one card and exit")
    ap.add_argument("--sleep", type=float, default=5.0,
                    help="seconds between calls (default 5; free tiers are rate-limited)")
    args = ap.parse_args()

    twins = sorted(TWINS.glob("*.json"))
    if not twins:
        sys.exit(f"no cards in {TWINS} - run scripts/03_export.py first")

    if args.show:
        path = TWINS / f"{args.show}.json"
        if not path.exists():
            sys.exit(f"no card {path}")
        for m in prompt_for(json.loads(path.read_text())):
            print(f"--- {m['role']} ---\n{m['content']}")
        return 0

    base_url = os.environ.get("LLM_BASE_URL")
    api_key = os.environ.get("LLM_API_KEY")
    model = os.environ.get("LLM_MODEL")
    if not (base_url and api_key and model):
        sys.exit("set LLM_BASE_URL, LLM_API_KEY and LLM_MODEL in .env (see .env.example)")

    cache: dict = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    made = skipped = patched = 0
    for path in twins:
        card = json.loads(path.read_text())
        if not card.get("verdict"):
            continue    # no verdict block (e.g. --no-climate export); nothing to narrate
        key = path.stem
        if key not in cache or args.force:
            if args.limit is not None and made >= args.limit:
                skipped += 1
                continue
            if made:
                time.sleep(args.sleep)
            text = complete(prompt_for(card), base_url, api_key, model)
            words = len(text.split())
            flag = f"  ! {words} words, review extra carefully" if words > WORD_LIMIT + 30 else ""
            print(f"{key} ({words} words){flag}\n  {text}\n")
            cache[key] = dict(text=text, model=model)
            CACHE.write_text(json.dumps(cache, indent=1))   # keep progress per card
            made += 1
        card["verdict"]["prose"] = dict(cache[key])
        path.write_text(json.dumps(card, separators=(",", ":"), allow_nan=False))
        patched += 1

    print(f"{made} generated, {patched} cards patched, {len(cache)} in {CACHE.name}"
          + (f", {skipped} still missing (--limit)" if skipped else ""))
    if made:
        print("Review every paragraph above against its card, then "
              "`python scripts/data.py push data/index/verdicts.json` and post on the Team log.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
