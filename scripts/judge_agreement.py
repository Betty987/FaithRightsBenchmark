#!/usr/bin/env python3
"""Inter-judge agreement on a random sample of run-1 responses.

The main analysis uses cross-model judging (Claude judges GPT, GPT judges Claude).
Here a stratified random sample of each model's responses is also scored by the
second judge, so every sampled response has two independent judgements. We report
quadratic-weighted Cohen's kappa per rubric dimension, Spearman correlation of the
protective and risk totals, and the mean difference between judges (a check for
self-preference; Panickssery et al., 2024).
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import cohen_kappa_score


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "robust"
RES = ROOT / "results" / "robust"
OUT = RES / "stats"
sys.path.insert(0, str(ROOT / "scripts"))
from judge_responses import SCORE_FIELDS, write_csv  # noqa: E402

JUDGES = {
    "claude": ("anthropic", "claude-haiku-4-5-20251001"),
    "gpt": ("openai-compatible", "gpt-4.1-mini"),
}
# model key -> (main judge used in the analysis, second judge for agreement)
PAIRS = {"gpt_4_1_mini": ("claude", "gpt"), "claude_haiku_4_5": ("gpt", "claude")}


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-model", type=int, default=115, help="Responses sampled per model (5 per identity).")
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    work = DATA / "work"
    prompts = {r["id"]: r for r in read_jsonl(DATA / "prompts.jsonl")}
    rows = []

    for key, (main_judge, second) in PAIRS.items():
        responses = read_jsonl(DATA / f"responses_{key}_run1.jsonl")
        df = pd.DataFrame(responses)
        df["identity"] = df.id.map(lambda i: prompts[i]["identity_id"])
        per_identity = max(1, args.per_model // df.identity.nunique())
        # Shuffle once, then take the first rows per identity, so each identity
        # gets a different random set of scenarios.
        sample = df.sample(frac=1, random_state=args.seed).groupby("identity").head(per_identity)
        inp = work / f"agreement_sample_{key}.jsonl"
        with inp.open("w", encoding="utf-8") as f:
            for r in sample.to_dict("records"):
                f.write(json.dumps({k: r[k] for k in ("id", "model", "provider", "response")}, ensure_ascii=False) + "\n")
        out = RES / f"agreement_judge_{second}_on_{key}_run1.jsonl"
        provider, model = JUDGES[second]
        subprocess.run([sys.executable, str(ROOT / "scripts" / "judge_responses.py"),
                        "--responses", str(inp), "--prompts", str(DATA / "prompts.jsonl"),
                        "--output", str(out), "--judge-provider", provider, "--judge-model", model,
                        "--sleep", "0"], cwd=ROOT, check=True)
        write_csv(out, out.with_suffix(".csv"))

        a = pd.read_csv(RES / f"judge_{main_judge}_on_{key}_run1.csv").set_index("id")
        b = pd.read_csv(out.with_suffix(".csv")).set_index("id")
        common = a.index.intersection(b.index)
        a, b = a.loc[common], b.loc[common]
        for field in SCORE_FIELDS + ["protective_ordinal_score", "risk_ordinal_score"]:
            x, y = a[field].astype(int), b[field].astype(int)
            if field in SCORE_FIELDS:
                kappa = cohen_kappa_score(x, y, weights="quadratic", labels=[0, 1, 2, 3]) if (x.nunique() > 1 or y.nunique() > 1) else np.nan
                exact = float((x == y).mean())
                within1 = float(((x - y).abs() <= 1).mean())
                rho = np.nan
            else:
                kappa, exact, within1 = np.nan, np.nan, np.nan
                rho = stats.spearmanr(x, y).statistic
            rows.append({"responses_of": key, "main_judge": main_judge, "second_judge": second,
                         "field": field, "n": len(common), "weighted_kappa": kappa,
                         "exact_agreement": exact, "within_1": within1, "spearman": rho,
                         "mean_main": x.mean(), "mean_second": y.mean(),
                         "second_minus_main": y.mean() - x.mean(),
                         "wilcoxon_p": stats.wilcoxon(y - x).pvalue if (y - x).abs().sum() > 0 else 1.0})
    res = pd.DataFrame(rows)
    res.to_csv(OUT / "judge_agreement.csv", index=False)
    print(res.round(3).to_string())


if __name__ == "__main__":
    main()
