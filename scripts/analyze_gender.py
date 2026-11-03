#!/usr/bin/env python3
"""Compare man vs. woman versions of the same prompts (gender check).

The man batch (data/robust/gender_prompts.jsonl, files tagged man_) covers a
subset of scenarios and identities. Each man cell (scenario x identity, mean of
3 runs) is paired with the identical woman cell from the main repeated-sample run.
"""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "robust"
RES = ROOT / "results" / "robust"
OUT = RES / "stats"
MODELS = {"GPT-4.1 Mini": ("gpt_4_1_mini", "claude"), "Claude Haiku 4.5": ("claude_haiku_4_5", "gpt")}
RUNS = (1, 2, 3)
REDIRECT = r"outside (?:of )?work|appropriate outlets|best to comply|important to comply|respect (?:your|the) manager"
SEED = 20261028


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load(key, judge, tag, keep_ids=None):
    frames = []
    for run in RUNS:
        j = pd.read_csv(RES / f"judge_{judge}_on_{tag}{key}_run{run}.csv")
        resp = {r["id"]: r["response"] for r in read_jsonl(DATA / f"responses_{tag}{key}_run{run}.jsonl")}
        j["response"] = j["id"].map(resp)
        j["run"] = run
        frames.append(j)
    d = pd.concat(frames, ignore_index=True)
    parts = d["id"].str.split("__")
    d["scenario"], d["identity"], d["gender"] = parts.str[0], parts.str[1], parts.str[2]
    if keep_ids is not None:
        d = d[d["id"].isin(keep_ids)]
    return d


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    man_ids = {r["id"] for r in read_jsonl(DATA / "gender_prompts.jsonl")}
    woman_ids = {i.replace("__man__", "__woman__") for i in man_ids}
    rows, scen_rows, robust_rows, redirect_rows = [], [], [], []

    for model, (key, judge) in MODELS.items():
        m = load(key, judge, "man_")
        w = load(key, judge, "", woman_ids)
        d = pd.concat([m, w], ignore_index=True)
        cells = d.groupby(["scenario", "identity", "gender"])[["protective_ordinal_score", "risk_ordinal_score"]].mean().unstack("gender")
        for metric, label in [("protective_ordinal_score", "protective"), ("risk_ordinal_score", "risk")]:
            diff = (cells[(metric, "woman")] - cells[(metric, "man")]).values
            boot = [diff[rng.integers(0, len(diff), len(diff))].mean() for _ in range(10000)]
            p = stats.wilcoxon(diff).pvalue if np.any(diff != 0) else 1.0
            rows.append({"model": model, "score": label, "n_cells": len(diff),
                         "woman_mean": cells[(metric, "woman")].mean(), "man_mean": cells[(metric, "man")].mean(),
                         "woman_minus_man": diff.mean(), "ci_low": np.percentile(boot, 2.5),
                         "ci_high": np.percentile(boot, 97.5), "wilcoxon_p": p,
                         "cells_woman_higher": int((diff > 0).sum()), "cells_man_higher": int((diff < 0).sum())})
        sc = d.groupby(["scenario", "gender"]).protective_ordinal_score.mean().unstack()
        for scen, r in sc.iterrows():
            scen_rows.append({"model": model, "scenario": scen, "woman": r["woman"], "man": r["man"],
                              "woman_minus_man": r["woman"] - r["man"]})
        # Cells where the gender difference held in every run.
        per_run = d.pivot_table(index=["scenario", "identity", "run"], columns="gender", values="protective_ordinal_score")
        for (scen, ident), g in per_run.groupby(level=[0, 1]):
            if g["woman"].min() > g["man"].max() or g["man"].min() > g["woman"].max():
                robust_rows.append({"model": model, "scenario": scen, "identity": ident,
                                    "woman_runs": "/".join(str(int(v)) for v in g["woman"]),
                                    "man_runs": "/".join(str(int(v)) for v in g["man"]),
                                    "higher": "woman" if g["woman"].mean() > g["man"].mean() else "man"})
        # Does the religion pattern (keep faith outside work) also hold for men?
        ft = d[d.scenario == "faith_conversation_ban"].copy()
        ft["hit"] = ft["response"].fillna("").str.lower().str.contains(REDIRECT, regex=True)
        per = ft.groupby(["gender", "identity"]).hit.mean().unstack("gender")
        per["model"] = model
        redirect_rows.append(per.reset_index())

    pd.DataFrame(rows).to_csv(OUT / "gender_overall.csv", index=False)
    pd.DataFrame(scen_rows).to_csv(OUT / "gender_by_scenario.csv", index=False)
    pd.DataFrame(robust_rows).to_csv(OUT / "gender_robust_cells.csv", index=False)
    pd.concat(redirect_rows).to_csv(OUT / "gender_redirect_pattern.csv", index=False)
    pd.set_option("display.width", 200)
    print(pd.DataFrame(rows).round(3).to_string())
    print(pd.DataFrame(scen_rows).round(2).to_string())
    print(pd.DataFrame(robust_rows).to_string())
    print(pd.concat(redirect_rows).round(2).to_string())


if __name__ == "__main__":
    main()
