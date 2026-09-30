#!/usr/bin/env python3
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROMPTS_PATH = ROOT / "data" / "prompts.jsonl"
OUT_PATH = ROOT / "data" / "pilot_prompts.jsonl"

PILOT_IDENTITIES = {"christian", "muslim", "jewish", "sikh", "baseline"}
PILOT_PHRASING = "v1"


def main() -> None:
    rows = []
    with PROMPTS_PATH.open(encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            if row["identity_id"] in PILOT_IDENTITIES and row["phrasing_id"] == PILOT_PHRASING:
                rows.append(row)

    with OUT_PATH.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Wrote {len(rows)} pilot prompts to {OUT_PATH}")


if __name__ == "__main__":
    main()
