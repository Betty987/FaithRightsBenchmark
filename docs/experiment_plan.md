# Experiment Plan

## Experiment 1: Single-Model Pilot

Purpose: verify that the prompts produce meaningful variation and that the scoring categories work.

Steps:

1. Generate prompts with `python3 scripts/generate_prompts.py`.
2. Select 24 prompts: 8 domains x 3 identities, plus baselines if possible.
3. Run one model manually or through an API.
4. Store outputs in `data/pilot_responses.jsonl`.
5. Run keyword scoring and inspect large differences.

Recommended identities for the first pilot:

- Christian
- Muslim
- Jewish
- Sikh
- baseline

Why these first: they are likely to reveal differences in workplace clothing, prayer/time, scheduling, and discrimination advice.

## Experiment 2: Full Identity Sweep

Purpose: test whether unequal support appears across the full identity set.

Run:

- 8 domains
- 10 identities including baseline
- 3 phrasings
- 1 response per prompt

Total: 240 responses per model.

Key metrics:

- average protective score by identity
- average risk score by identity
- rights-language rate by identity
- stereotype-insertion rate by identity
- largest faith gap within each domain

## Experiment 3: Multi-Model Comparison

Purpose: test whether patterns are model-specific or shared across providers.

Suggested models:

- GPT-4o or GPT-4.1
- Gemini 2.5 Flash or Pro
- Claude Sonnet
- Llama open-weight model
- Mistral/Mixtral model

Report:

- Which model has the lowest overall faith gap?
- Which model has the highest rights-language rate?
- Which model has the highest risk score?
- Which identities have consistently lower protective scores across models?

## Experiment 4: Stability Test

Purpose: determine whether results are repeatable.

Run each prompt 3-5 times at low temperature.

Report:

- within-prompt variance
- whether faith gaps persist across runs
- whether risky categories appear repeatedly or only once

## Experiment 5: Baseline Harm Audit

Purpose: identify concrete harm cases.

For each scenario, compare faith-conditioned responses to the baseline.

Flag cases where a faith-conditioned response has:

- lower protective score than baseline
- no rights language when baseline has rights language
- no documentation advice when baseline has documentation advice
- stereotype insertion not present in baseline
- burden shifting not present in baseline

## Suggested First Research Claim

Religious bias in LLMs can appear as unequal access to practical rights-based guidance, not only as stereotyping or conversion preference.

## Suggested Tables

1. Benchmark composition: domains, identities, phrasings.
2. Model-level protective and risk scores.
3. Identity-level faith gaps.
4. Top harm cases with short response excerpts.
5. Stability across repeated generations.
