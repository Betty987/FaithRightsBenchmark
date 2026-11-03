#!/usr/bin/env python3
"""Collect several independent samples per prompt for each model, then judge them.

Each run sends every prompt in --prompts once to each model at --temperature and
writes data/robust/responses_<model>_run<k>.jsonl. Each run's answers are then
scored by the other model (cross-model judging) into
results/robust/judge_<judge>_on_<model>_run<k>.jsonl/.csv.

Work is split into --workers chunks per model and run so the API calls proceed in
parallel. Every step resumes: re-running the script only fills in missing rows.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

MODELS = {
    "gpt_4_1_mini": {"provider": "openai-compatible", "model": "gpt-4.1-mini"},
    "claude_haiku_4_5": {"provider": "anthropic", "model": "claude-haiku-4-5-20251001"},
}
# Cross-model judging: each model's answers are scored by the other model.
JUDGE_OF = {"gpt_4_1_mini": "claude_haiku_4_5", "claude_haiku_4_5": "gpt_4_1_mini"}
JUDGE_SHORT = {"gpt_4_1_mini": "gpt", "claude_haiku_4_5": "claude"}


def read_jsonl(path: Path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def split(rows, n):
    size = -(-len(rows) // n)
    return [rows[i:i + size] for i in range(0, len(rows), size)]


def run_parallel(commands):
    procs = [subprocess.Popen(cmd, cwd=ROOT, stdout=log.open("w"), stderr=subprocess.STDOUT)
             for cmd, log in commands]
    codes = [p.wait() for p in procs]
    for (cmd, log), code in zip(commands, codes):
        if code != 0:
            print(f"  step failed (exit {code}); see {log}")
    return all(code == 0 for code in codes)


def merge(parts, out_path: Path, order):
    rows = {}
    for part in parts:
        for row in read_jsonl(part):
            rows[row["id"]] = row
    merged = [rows[i] for i in order if i in rows]
    write_jsonl(out_path, merged)
    return len(merged)


def existing_parts(work: Path, pattern: str):
    return sorted(work.glob(pattern))


def collect(prompts_path, runs, temperature, workers, work, tag=""):
    """Collect all (model, run) combinations concurrently."""
    prompts = read_jsonl(prompts_path)
    order = [p["id"] for p in prompts]
    commands, jobs = [], []
    for run in runs:
        for key, cfg in MODELS.items():
            out = ROOT / "data" / "robust" / f"responses_{tag}{key}_run{run}.jsonl"
            # Fold in partial results from any earlier, interrupted attempt.
            parts = [out] + existing_parts(work, f"responses_{tag}{key}_run{run}_*.jsonl")
            merge(parts, out, order)
            done = {r["id"] for r in read_jsonl(out)}
            todo = [p for p in prompts if p["id"] not in done]
            jobs.append((key, run, out))
            if not todo:
                continue
            attempt = len(existing_parts(work, f"prompts_{tag}{key}_run{run}_*.jsonl"))
            for i, chunk in enumerate(split(todo, workers)):
                tag_i = f"{tag}{key}_run{run}_{attempt + i}"
                inp = work / f"prompts_{tag_i}.jsonl"
                write_jsonl(inp, chunk)
                commands.append(([sys.executable, str(SCRIPTS / "collect_responses.py"),
                                  "--input", str(inp), "--output", str(work / f"responses_{tag_i}.jsonl"),
                                  "--provider", cfg["provider"], "--model", cfg["model"],
                                  "--temperature", str(temperature), "--sleep", "0"],
                                 work / f"log_collect_{tag_i}.txt"))
    print(f"collect: launching {len(commands)} workers")
    run_parallel(commands)
    for key, run, out in jobs:
        parts = [out] + existing_parts(work, f"responses_{tag}{key}_run{run}_*.jsonl")
        n = merge(parts, out, order)
        print(f"run {run} {key}: {n}/{len(order)} responses")


def judge(prompts_path, runs, workers, work, tag=""):
    """Judge all (model, run) combinations concurrently with the other model."""
    sys.path.insert(0, str(SCRIPTS))
    import judge_responses

    commands, jobs = [], []
    for run in runs:
        for key in MODELS:
            judge_key = JUDGE_OF[key]
            cfg = MODELS[judge_key]
            responses = read_jsonl(ROOT / "data" / "robust" / f"responses_{tag}{key}_run{run}.jsonl")
            order = [r["id"] for r in responses]
            out = ROOT / "results" / "robust" / f"judge_{JUDGE_SHORT[judge_key]}_on_{tag}{key}_run{run}.jsonl"
            parts = [out] + existing_parts(work, f"judged_{tag}{key}_run{run}_*.jsonl")
            merge(parts, out, order)
            done = {r["id"] for r in read_jsonl(out)}
            todo = [r for r in responses if r["id"] not in done]
            jobs.append((key, run, out, order, judge_key))
            if not todo:
                continue
            attempt = len(existing_parts(work, f"tojudge_{tag}{key}_run{run}_*.jsonl"))
            for i, chunk in enumerate(split(todo, workers)):
                tag_i = f"{tag}{key}_run{run}_{attempt + i}"
                inp = work / f"tojudge_{tag_i}.jsonl"
                write_jsonl(inp, chunk)
                commands.append(([sys.executable, str(SCRIPTS / "judge_responses.py"),
                                  "--responses", str(inp), "--prompts", str(prompts_path),
                                  "--output", str(work / f"judged_{tag_i}.jsonl"),
                                  "--judge-provider", cfg["provider"],
                                  "--judge-model", cfg["model"], "--sleep", "0"],
                                 work / f"log_judge_{tag_i}.txt"))
    print(f"judge: launching {len(commands)} workers")
    run_parallel(commands)
    for key, run, out, order, judge_key in jobs:
        parts = [out] + existing_parts(work, f"judged_{tag}{key}_run{run}_*.jsonl")
        n = merge(parts, out, order)
        judge_responses.write_csv(out, out.with_suffix(".csv"))
        print(f"run {run} {key}: {n}/{len(order)} judged by {judge_key}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect and judge repeated samples.")
    parser.add_argument("--prompts", default="data/robust/prompts.jsonl")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--stage", choices=["collect", "judge", "all"], default="all")
    parser.add_argument("--tag", default="", help="Prefix for output files, e.g. 'man_' for a separate batch.")
    args = parser.parse_args()

    prompts_path = (ROOT / args.prompts).resolve()
    work = ROOT / "data" / "robust" / "work"
    work.mkdir(parents=True, exist_ok=True)
    runs = list(range(1, args.runs + 1))
    if args.stage in {"collect", "all"}:
        collect(prompts_path, runs, args.temperature, args.workers, work, args.tag)
    if args.stage in {"judge", "all"}:
        judge(prompts_path, runs, args.workers, work, args.tag)


if __name__ == "__main__":
    main()
