#!/usr/bin/env python3
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "data" / "prompt_specs.json"
OUT_PATH = ROOT / "data" / "prompts.jsonl"
SAMPLE_RESPONSES_PATH = ROOT / "data" / "sample_responses.jsonl"


def build_prompt(prefix: str, scenario: str, suffix: str) -> str:
    parts = [prefix.strip(), scenario.strip() + suffix]
    return " ".join(part for part in parts if part).strip()


def main() -> None:
    spec = json.loads(SPEC_PATH.read_text())
    rows = []
    for template in spec["templates"]:
        for identity in spec["identities"]:
            for phrasing in spec["phrasings"]:
                row_id = f"{template['id']}__{identity['id']}__{phrasing['id']}"
                rows.append(
                    {
                        "id": row_id,
                        "benchmark": spec["benchmark"],
                        "version": spec["version"],
                        "template_id": template["id"],
                        "domain": template["domain"],
                        "identity_id": identity["id"],
                        "identity_label": identity["label"],
                        "phrasing_id": phrasing["id"],
                        "prompt": build_prompt(
                            identity["prefix"],
                            template["scenario"],
                            phrasing["suffix"],
                        ),
                    }
                )

    with OUT_PATH.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    sample_rows = []
    for row in rows[:6]:
        sample_rows.append(
            {
                "id": row["id"],
                "model": "example_model",
                "response": "Example placeholder response. Replace this with a real model output.",
            }
        )
    with SAMPLE_RESPONSES_PATH.open("w", encoding="utf-8") as f:
        for row in sample_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Wrote {len(rows)} prompts to {OUT_PATH}")
    print(f"Wrote sample response template to {SAMPLE_RESPONSES_PATH}")


if __name__ == "__main__":
    main()
