# FaithRightsBench

FaithRightsBench tests whether LLM advice on religious accommodation at work and school changes with the user's stated religion.

Each prompt describes a fixed conflict, for example a manager banning talk about faith or a school refusing a prayer room. Only the first sentence changes between conditions:

```text
I am a Sikh woman. My manager has now told me to stop all religious conversation at work, ...
I am a Baptist woman. My manager has now told me to stop all religious conversation at work, ...
I am a woman. My manager has now told me to stop all religious conversation at work, ...
```

Because the rest of the prompt is identical, systematic differences in the advice can be attributed to the religion named.

## Design

| | |
|---|---|
| Scenarios | 19: 13 workplace and 6 school, including 2 written from a manager's or professor's point of view |
| Identities | 23: 16 Christian denominations, 6 other faiths (Muslim, Jewish, Sikh, Hindu, Buddhist, Baha'i), and no religion stated |
| Prompts | 19 × 23 = 437, written as a woman |
| Models | GPT-4.1 Mini (`gpt-4.1-mini`) and Claude Haiku 4.5 (`claude-haiku-4-5-20251001`) |
| Sampling | each prompt asked 3 times per model at temperature 0.7, giving 2,622 responses |
| Gender check | 6 scenarios × 10 identities written as a man, 3 runs per model, giving 360 responses |
| Scoring | LLM judge with a 12-dimension rubric, each dimension scored 0–3 ([data/judge_rubric.md](data/judge_rubric.md)). Each model is judged by the other model. |

The rubric gives two totals, each out of 18:

- **Protective score** (higher is better): supportiveness, rights-based guidance, actionability, institutional referral, documentation advice, faith-specific accuracy.
- **Risk score** (lower is better): minimization, burden shifting, stereotype insertion, sincerity questioning, safety/security framing, religious accuracy error.

## Repository layout

```text
data/
  prompt_specs_practice.json   13 scenarios and the 23 identities
  prompt_specs_stress.json     6 further scenarios (same identities)
  judge_rubric.md              rubric given to the LLM judge
  robust/
    prompts.jsonl              the 437 prompts
    gender_prompts.jsonl       the 60 man prompts
    responses_{model}_run{k}.jsonl        model responses (woman)
    responses_man_{model}_run{k}.jsonl    model responses (man)
results/robust/
  judge_{judge}_on_{model}_run{k}.jsonl/.csv   judge scores per response
  agreement_judge_*                            second-judge scores for the agreement check
  stats/                                       analysis outputs (CSV and summary.json)
annotation/
  human_validation_sheet.csv   60 responses for human scoring (model hidden)
scripts/                       see below
docs/
  arr_paper/                   paper draft (ACL Rolling Review template)
  supervisor_report_repeated.tex
```

## Reproducing the results

Requires Python 3.9 or newer.

```bash
pip install -r requirements.txt
cp .env.example .env    # then add your OpenAI and Anthropic API keys
```

| Step | Command | Calls APIs |
|---|---|---|
| 1. Build prompts | `python3 scripts/build_prompts.py` | no |
| 2. Collect and judge 3 runs (woman) | `python3 scripts/run_repeated_samples.py` | yes |
| 3. Collect and judge the man prompts | `python3 scripts/run_repeated_samples.py --prompts data/robust/gender_prompts.jsonl --tag man_` | yes |
| 4. Main analysis | `python3 scripts/analyze_repeated.py` | no |
| 5. Run-to-run standard deviations | `python3 scripts/run_variability.py` | no |
| 6. Gender comparison | `python3 scripts/analyze_gender.py` | no |
| 7. Judge agreement check | `python3 scripts/judge_agreement.py` | yes |
| 8. Human validation | `python3 scripts/make_human_validation_sheet.py score` (after the sheet is filled in) | no |

All responses and judge scores are included, so steps 4–6 can be run without API keys. `collect_responses.py` and `judge_responses.py` are the single-model tools that `run_repeated_samples.py` calls.

## Analysis

- **Unit of analysis:** a cell is one scenario × identity combination, averaged over the 3 runs.
- **Identity effect:** Friedman test with scenarios as blocks; Kendall's W as the effect size.
- **Christian vs. other faiths:** permutation test over identity labels; scenario-bootstrap 95% confidence intervals.
- **Run-to-run variability:** standard deviation over the 3 runs, ICC(1), and rank stability of the identities between runs.
- **Advice patterns:** regular expressions for specific advice types, for example "keep your faith outside work", with a Holm correction.

## Status

The human validation of the LLM judge is in progress.
