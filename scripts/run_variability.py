#!/usr/bin/env python3
"""Run-to-run variability: standard deviation of judge scores across the 3 runs.

For every cell (scenario x identity) the 3 run scores give a mean and a sample
standard deviation (ddof=1). Outputs, in results/robust/stats/:
  run_sd_cells_{model}.csv     mean and SD per cell
  run_sd_scenarios_{model}.csv mean of the cell SDs per scenario
  run_sd_identities_{model}.csv identity means per run, and SD of those run means
  run_sd_summary.csv           one row per model and score
"""
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results" / "robust"
OUT = RES / "stats"
MODELS = {"gpt_4_1_mini": "claude", "claude_haiku_4_5": "gpt"}
SCORES = {"protective_ordinal_score": "protective", "risk_ordinal_score": "risk"}
RUNS = (1, 2, 3)


def load(key, judge):
    frames = []
    for run in RUNS:
        d = pd.read_csv(RES / f"judge_{judge}_on_{key}_run{run}.csv")
        d["run"] = run
        frames.append(d)
    d = pd.concat(frames, ignore_index=True)
    parts = d["id"].str.split("__")
    d["scenario"], d["identity"] = parts.str[0], parts.str[1]
    return d.rename(columns=SCORES)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    summary = []
    for key, judge in MODELS.items():
        d = load(key, judge)
        cells = d.groupby(["scenario", "identity"])[list(SCORES.values())].agg(["mean", "std"])
        cells.columns = [f"{s}_{stat}" for s, stat in cells.columns]
        cells.reset_index().to_csv(OUT / f"run_sd_cells_{key}.csv", index=False)
        cells.groupby("scenario").mean().reset_index().to_csv(OUT / f"run_sd_scenarios_{key}.csv", index=False)

        runs = d.pivot_table(index="identity", columns="run", values="protective", aggfunc="mean")
        runs["mean"] = runs[list(RUNS)].mean(axis=1)
        runs["sd_of_run_means"] = runs[list(RUNS)].std(axis=1)
        runs.reset_index().to_csv(OUT / f"run_sd_identities_{key}.csv", index=False)

        for score in SCORES.values():
            sd = cells[f"{score}_std"]
            summary.append({"model": key, "score": score, "n_cells": len(sd),
                            "mean_sd": sd.mean(), "median_sd": sd.median(), "max_sd": sd.max(),
                            "share_sd_zero": (sd == 0).mean(),
                            "mean_sd_of_identity_run_means": runs["sd_of_run_means"].mean() if score == "protective" else None})
    res = pd.DataFrame(summary)
    res.to_csv(OUT / "run_sd_summary.csv", index=False)
    print(res.round(3).to_string())


if __name__ == "__main__":
    main()
