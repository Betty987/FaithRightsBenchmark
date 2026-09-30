#!/usr/bin/env python3
import csv
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List


NUMERIC_FIELDS = [
    "rights_language",
    "accommodation_language",
    "documentation_advice",
    "institutional_escalation",
    "legal_or_policy_referral",
    "emotional_validation",
    "practical_steps",
    "minimization",
    "burden_shifting",
    "stereotype_insertion",
    "sincerity_questioning",
    "safety_or_security_framing",
    "religious_accuracy_error",
    "protective_score",
    "risk_score",
]


def read_csv(path: Path) -> List[Dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def mean(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python3 scripts/analyze_scores.py SCORES.csv OUT.csv")

    in_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])
    rows = read_csv(in_path)

    groups = defaultdict(list)
    for row in rows:
        key = (row["model"], row["identity_id"], row["identity_label"])
        groups[key].append(row)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["model", "identity_id", "identity_label", "n", *NUMERIC_FIELDS]
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for (model, identity_id, identity_label), group_rows in sorted(groups.items()):
            summary = {
                "model": model,
                "identity_id": identity_id,
                "identity_label": identity_label,
                "n": len(group_rows),
            }
            for field in NUMERIC_FIELDS:
                summary[field] = f"{mean([float(row[field]) for row in group_rows]):.3f}"
            writer.writerow(summary)

    print(f"Wrote summary to {out_path}")


if __name__ == "__main__":
    main()
