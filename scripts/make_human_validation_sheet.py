#!/usr/bin/env python3
"""Create a blinded human-annotation sheet and score human-judge agreement.

  make:  sample N run-1 responses (half per model, spread across identities and
         scenarios), shuffle them, hide the model name, and write
         annotation/human_validation_sheet.csv plus a private key file.
  score: after annotators fill in the 0-3 columns, compare each annotator with the
         LLM judge (quadratic-weighted kappa per dimension, Spearman on totals) and,
         if two annotators are present, with each other.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import cohen_kappa_score


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "robust"
RES = ROOT / "results" / "robust"
ANN = ROOT / "annotation"
SHEET = ANN / "human_validation_sheet.csv"
KEY = ANN / "human_validation_key.csv"
DIMS = ["supportiveness", "rights_based_guidance", "actionability", "institutional_referral",
        "documentation_advice", "religious_specific_accuracy", "minimization", "burden_shifting",
        "stereotype_insertion", "sincerity_questioning", "safety_or_security_framing",
        "religious_accuracy_error"]
MAIN_JUDGE = {"gpt_4_1_mini": "claude", "claude_haiku_4_5": "gpt"}


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def make(n: int, seed: int) -> None:
    prompts = {r["id"]: r for r in read_jsonl(DATA / "prompts.jsonl")}
    rows = []
    for key in MAIN_JUDGE:
        df = pd.DataFrame(read_jsonl(DATA / f"responses_{key}_run1.jsonl"))
        df["identity"] = df.id.map(lambda i: prompts[i]["identity_id"])
        df["scenario"] = df.id.map(lambda i: prompts[i]["template_id"])
        # Round-robin over identities so every identity is represented.
        df = df.sample(frac=1, random_state=seed)
        picked = []
        for _, g in df.groupby("identity"):
            picked.append(g.iloc[0])
        picked = pd.DataFrame(picked)
        extra = df[~df.id.isin(picked.id)].head(max(0, n // 2 - len(picked)))
        sel = pd.concat([picked, extra]).head(n // 2)
        for r in sel.to_dict("records"):
            rows.append({"model_key": key, "id": r["id"], "prompt": prompts[r["id"]]["prompt"], "response": r["response"]})
    sheet = pd.DataFrame(rows).sample(frac=1, random_state=seed).reset_index(drop=True)
    sheet.insert(0, "item", [f"H{i + 1:03d}" for i in range(len(sheet))])
    ANN.mkdir(exist_ok=True)
    sheet[["item", "model_key", "id"]].to_csv(KEY, index=False)
    out = sheet[["item", "prompt", "response"]].copy()
    for d in DIMS:
        out[d] = ""
    out["annotator"] = ""
    out["notes"] = ""
    out.to_csv(SHEET, index=False)
    print(f"Wrote {len(out)} items to {SHEET} (model hidden; key in {KEY})")


def kappa(x, y):
    return cohen_kappa_score(x, y, weights="quadratic", labels=[0, 1, 2, 3])


def score(files) -> None:
    key = pd.read_csv(KEY)
    judge = []
    for mk, js in MAIN_JUDGE.items():
        j = pd.read_csv(RES / f"judge_{js}_on_{mk}_run1.csv")
        judge.append(j.assign(model_key=mk))
    judge = pd.concat(judge).set_index("id")
    sheets = []
    for f in files:
        s = pd.read_csv(f).merge(key, on="item")
        s = s.dropna(subset=DIMS)
        s["annotator"] = s["annotator"].fillna(Path(f).stem)
        sheets.append(s)
    rows = []
    for s in sheets:
        jj = judge.loc[s.id]
        for d in DIMS:
            rows.append({"comparison": f"{s.annotator.iloc[0]} vs LLM judge", "dimension": d, "n": len(s),
                         "weighted_kappa": kappa(s[d].astype(int), jj[d].astype(int))})
        for tot, part in [("protective", DIMS[:6]), ("risk", DIMS[6:])]:
            rows.append({"comparison": f"{s.annotator.iloc[0]} vs LLM judge", "dimension": f"{tot} total",
                         "n": len(s), "spearman": stats.spearmanr(s[part].sum(axis=1), jj[part].sum(axis=1)).statistic})
    if len(sheets) == 2:
        a, b = sheets[0].set_index("item"), sheets[1].set_index("item")
        common = a.index.intersection(b.index)
        for d in DIMS:
            rows.append({"comparison": "annotator 1 vs annotator 2", "dimension": d, "n": len(common),
                         "weighted_kappa": kappa(a.loc[common, d].astype(int), b.loc[common, d].astype(int))})
    res = pd.DataFrame(rows)
    res.to_csv(RES / "stats" / "human_agreement.csv", index=False)
    print(res.round(3).to_string())


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("make"); m.add_argument("--n", type=int, default=60); m.add_argument("--seed", type=int, default=11)
    sc = sub.add_parser("score"); sc.add_argument("files", nargs="+", help="Completed annotation CSVs (one per annotator)")
    args = parser.parse_args()
    make(args.n, args.seed) if args.cmd == "make" else score(args.files)


if __name__ == "__main__":
    main()
