#!/usr/bin/env python3
"""Build the FaithRightsBench prompt files from the scenario specs.

Writes:
  data/robust/prompts.jsonl         19 scenarios x 23 identities, woman, wording v1 (437 prompts)
  data/robust/gender_prompts.jsonl  6 scenarios x 10 identities, man, wording v1 (60 prompts)

The 19 scenarios come from two specs: 13 in data/prompt_specs_practice.json and
6 in data/prompt_specs_stress.json. Both specs define the same 23 identities.
"""
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "robust"
SPECS = [
    (DATA / "prompt_specs_practice.json", None),
    (DATA / "prompt_specs_stress.json", {
        "exam_no_makeup", "customer_facing_attire", "holiday_leave_competing",
        "prayer_break_backlash", "manager_frontdesk_attire", "professor_makeup_exam",
    }),
]
PHRASING = "v1"
GENDER_SCENARIOS = {
    "head_covering_uniform", "modest_dress_pe", "faith_conversation_ban",
    "school_prayer_space", "daylight_fast_safety", "alcohol_client_dinners",
}
GENDER_IDENTITIES = {
    "muslim", "jewish", "sikh", "hindu", "catholic", "baptist", "pentecostal",
    "evangelical", "nondenominational_christian", "baseline",
}


def person_phrase(gender_prefix: str) -> str:
    # "I am a Muslim woman." -> "a Muslim woman"
    return gender_prefix.strip().removeprefix("I am ").rstrip(".")


def build_prompt(template: dict, gender_prefix: str, suffix: str) -> str:
    if template["perspective"] == "third_person":
        return template["scenario"].format(person=person_phrase(gender_prefix)) + suffix
    return " ".join(part for part in [gender_prefix.strip(), template["scenario"] + suffix] if part)


def rows_for(spec_path: Path, templates, gender: str):
    spec = json.loads(spec_path.read_text())
    phrasing = next(p for p in spec["phrasings"] if p["id"] == PHRASING)
    genders = {g["id"]: g for g in spec["genders"]}
    for template in spec["templates"]:
        if templates is not None and template["id"] not in templates:
            continue
        for identity in spec["identities"]:
            prefix = identity["gender_prefixes"][gender]
            yield {
                "id": f"{template['id']}__{identity['id']}__{gender}__{PHRASING}",
                "benchmark": spec["benchmark"],
                "version": spec["version"],
                "template_id": template["id"],
                "domain": template["domain"],
                "perspective": template["perspective"],
                "identity_id": identity["id"],
                "identity_label": identity["label"],
                "gender_id": gender,
                "gender_label": genders[gender]["label"],
                "phrasing_id": PHRASING,
                "prompt": build_prompt(template, prefix, phrasing["suffix"]),
            }


def write(path: Path, rows) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Wrote {len(rows)} prompts to {path.relative_to(ROOT)}")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    main_rows = [r for spec, templates in SPECS for r in rows_for(spec, templates, "woman")]
    write(OUT / "prompts.jsonl", main_rows)
    man_rows = [r for spec, templates in SPECS for r in rows_for(spec, templates, "man")
                if r["template_id"] in GENDER_SCENARIOS and r["identity_id"] in GENDER_IDENTITIES]
    write(OUT / "gender_prompts.jsonl", man_rows)


if __name__ == "__main__":
    main()
