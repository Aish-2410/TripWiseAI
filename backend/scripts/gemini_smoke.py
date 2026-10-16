"""Manual smoke test for the real Gemini API (NOT part of the automated suite; uses a little quota).

    cd backend && PYTHONPATH=. python scripts/gemini_smoke.py

Reads GEMINI_API_KEY / GEMINI_MODEL from backend/.env or the environment. Never prints the key.
"""
from __future__ import annotations

import sys
from datetime import date

from app.ai import llm
from app.ai.engine import get_engine

SAMPLES = ["Could you put together a relaxed 4 day trip to Coorg from Hyderabad, budget around 15K, we are two", "Actually, make it Munnar instead, same budget",
           "any rooms at the Arth place in Hyderabad?"]


def main() -> int:
    st = llm.status()
    print(f"model: {st['model']}   key: {'set (hidden)' if st['configured'] else 'MISSING - add GEMINI_API_KEY to backend/.env'}")
    if not st["enabled"]:
        return 2
    ds = get_engine().ds
    ok = True
    for msg in SAMPLES:
        print("\n>", msg)
        try:
            raw = llm._generate(llm._prompt(msg, {}), llm._cfg())
            it = llm.Interpretation.model_validate_json(raw)
        except Exception as e:  # noqa: BLE001
            ok = False
            print("  FAILED:", type(e).__name__, llm._safe(e))
            continue
        print("  model said:", it.model_dump(exclude_none=True, exclude_defaults=True))
        print("  validated entities:", llm.to_entities(it, ds, date.today(), msg))
    print("\nResult:", "OK" if ok else "problems above (the app would fall back to the rule-based parser)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
