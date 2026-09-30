#!/usr/bin/env python3
import csv
from pathlib import Path
from typing import Dict, List


ROOT = Path(__file__).resolve().parents[1]
SUMMARY_FILES = [
    ROOT / "results" / "gemini_3_5_flash_lite_summary.csv",
    ROOT / "results" / "groq_gpt_oss_20b_summary.csv",
]
OUT_DIR = ROOT / "docs" / "assets"
COMBINED_CSV = ROOT / "results" / "model_comparison_scores.csv"

MODEL_LABELS = {
    "gemini-3.5-flash-lite": "Gemini 3.5 Flash Lite",
    "openai/gpt-oss-20b": "Groq GPT-OSS 20B",
}

IDENTITY_ORDER = ["baseline", "christian", "muslim", "jewish", "sikh"]
COLORS = {
    "baseline": "#6b7280",
    "christian": "#2563eb",
    "muslim": "#059669",
    "jewish": "#7c3aed",
    "sikh": "#d97706",
}


def read_rows() -> List[Dict]:
    rows = []
    for path in SUMMARY_FILES:
        if not path.exists():
            continue
        with path.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                row["model_label"] = MODEL_LABELS.get(row["model"], row["model"])
                rows.append(row)
    return rows


def write_combined(rows: List[Dict]) -> None:
    COMBINED_CSV.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "model",
        "model_label",
        "identity_id",
        "identity_label",
        "n",
        "protective_score",
        "risk_score",
        "rights_language",
        "emotional_validation",
        "stereotype_insertion",
    ]
    with COMBINED_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def draw_grouped_bar(rows: List[Dict], metric: str, title: str, output: Path) -> None:
    models = []
    for row in rows:
        if row["model_label"] not in models:
            models.append(row["model_label"])

    by_key = {
        (row["model_label"], row["identity_id"]): float(row[metric])
        for row in rows
    }
    labels = {
        row["identity_id"]: row["identity_label"]
        for row in rows
    }

    width = 980
    height = 560
    margin_left = 80
    margin_right = 30
    margin_top = 72
    margin_bottom = 96
    plot_w = width - margin_left - margin_right
    plot_h = height - margin_top - margin_bottom
    max_value = max(7.0 if metric == "protective_score" else 3.0, max(by_key.values()))

    group_w = plot_w / len(models)
    bar_gap = 8
    inner_w = group_w - 36
    bar_w = (inner_w - bar_gap * (len(IDENTITY_ORDER) - 1)) / len(IDENTITY_ORDER)

    def x_for(model_idx: int, identity_idx: int) -> float:
        return margin_left + model_idx * group_w + 18 + identity_idx * (bar_w + bar_gap)

    def y_for(value: float) -> float:
        return margin_top + plot_h - (value / max_value) * plot_h

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{width / 2}" y="34" text-anchor="middle" font-family="Arial, sans-serif" font-size="22" font-weight="700" fill="#111827">{title}</text>',
    ]

    for tick in range(0, int(max_value) + 1):
        y = y_for(tick)
        parts.append(f'<line x1="{margin_left}" y1="{y:.1f}" x2="{width - margin_right}" y2="{y:.1f}" stroke="#e5e7eb"/>')
        parts.append(f'<text x="{margin_left - 12}" y="{y + 4:.1f}" text-anchor="end" font-family="Arial, sans-serif" font-size="12" fill="#4b5563">{tick}</text>')

    parts.append(f'<line x1="{margin_left}" y1="{margin_top + plot_h}" x2="{width - margin_right}" y2="{margin_top + plot_h}" stroke="#374151"/>')
    parts.append(f'<line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{margin_top + plot_h}" stroke="#374151"/>')

    for model_idx, model in enumerate(models):
        for identity_idx, identity in enumerate(IDENTITY_ORDER):
            value = by_key.get((model, identity), 0)
            x = x_for(model_idx, identity_idx)
            y = y_for(value)
            h = margin_top + plot_h - y
            color = COLORS[identity]
            parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" fill="{color}" rx="2"/>')
            parts.append(f'<text x="{x + bar_w / 2:.1f}" y="{y - 5:.1f}" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" fill="#111827">{value:.2f}</text>')
        center = margin_left + model_idx * group_w + group_w / 2
        parts.append(f'<text x="{center:.1f}" y="{height - 54}" text-anchor="middle" font-family="Arial, sans-serif" font-size="14" font-weight="700" fill="#111827">{model}</text>')

    legend_x = margin_left
    legend_y = height - 28
    for idx, identity in enumerate(IDENTITY_ORDER):
        x = legend_x + idx * 165
        parts.append(f'<rect x="{x}" y="{legend_y - 11}" width="13" height="13" fill="{COLORS[identity]}" rx="2"/>')
        parts.append(f'<text x="{x + 19}" y="{legend_y}" font-family="Arial, sans-serif" font-size="13" fill="#374151">{labels.get(identity, identity)}</text>')

    parts.append("</svg>")
    output.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    rows = read_rows()
    if not rows:
        raise SystemExit("No summary files found. Run analyze_scores.py first.")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_combined(rows)
    draw_grouped_bar(
        rows,
        "protective_score",
        "Average Protective Score by Identity",
        OUT_DIR / "protective_scores.svg",
    )
    draw_grouped_bar(
        rows,
        "risk_score",
        "Average Risk Score by Identity",
        OUT_DIR / "risk_scores.svg",
    )
    print(f"Wrote {COMBINED_CSV}")
    print(f"Wrote {OUT_DIR / 'protective_scores.svg'}")
    print(f"Wrote {OUT_DIR / 'risk_scores.svg'}")


if __name__ == "__main__":
    main()
