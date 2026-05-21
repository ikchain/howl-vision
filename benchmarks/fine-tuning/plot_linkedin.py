"""Generate two LinkedIn-grade plots from results_p0_comparison.json.

Both plots make the same point: fine-tuning Gemma 4 with the narrative LoRA adapter
produced zero measurable delta versus the base model. Plots are designed for
LinkedIn (1200x675 = 1.78:1) on dark background to match the Howl Vision palette.
"""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).parent
DATA = json.loads((ROOT / "results_p0_comparison.json").read_text())

CLASS_LABELS = {
    "demodicosis": "Demodicosis",
    "Dermatitis": "Dermatitis",
    "Flea_Allergy": "Flea allergy",
    "Healthy": "Healthy",
    "ringworm": "Ringworm",
    "Hypersensitivity_Allergic_Dermatitis": "Hypersensitivity",
    "Scabies": "Scabies",
    "Fungal_infections": "Fungal",
}

BG = "#0a1525"
FG = "#e6eef7"
MUTED = "#7d93ad"
ACCENT_BASE = "#5dd9d9"
ACCENT_FT = "#ffa15a"
GRID = "#1c2a3f"


def setup_dark(ax):
    ax.set_facecolor(BG)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(colors=FG, labelsize=11)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def plot_grouped_bars(out_path: Path) -> None:
    classes_sorted = sorted(
        DATA["base"]["per_class"].items(),
        key=lambda kv: -kv[1]["f1"],
    )
    names = [CLASS_LABELS[k] for k, _ in classes_sorted]
    base_f1 = [v["f1"] for _, v in classes_sorted]
    ft_f1 = [DATA["narrative"]["per_class"][k]["f1"] for k, _ in classes_sorted]
    base_ci = np.array([v["ci"] for _, v in classes_sorted])
    base_err = np.vstack([np.array(base_f1) - base_ci[:, 0], base_ci[:, 1] - np.array(base_f1)])

    x = np.arange(len(names))
    width = 0.36

    fig, ax = plt.subplots(figsize=(12, 6.75), facecolor=BG)
    setup_dark(ax)

    ax.bar(x - width / 2, base_f1, width, color=ACCENT_BASE,
           label="Base Gemma 4 E4B-it", edgecolor="none")
    ax.bar(x + width / 2, ft_f1, width, color=ACCENT_FT,
           label="Fine-tuned LoRA (narrative)", edgecolor="none")
    ax.errorbar(x - width / 2, base_f1, yerr=base_err, fmt="none",
                ecolor=FG, alpha=0.45, capsize=4, capthick=1.2, elinewidth=1.2)

    ax.set_xticks(x)
    ax.set_xticklabels(names, color=FG, rotation=0, fontsize=11)
    ax.set_ylim(0, 1.08)
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(["0", "0.25", "0.50", "0.75", "1.00"], color=FG)
    ax.axhline(DATA["base"]["macro_f1"], color=MUTED, linewidth=1, linestyle="--", alpha=0.5)
    ax.text(7.4, DATA["base"]["macro_f1"] + 0.015,
            f"macro F1 = {DATA['base']['macro_f1']:.3f}",
            color=MUTED, fontsize=10, ha="right", va="bottom")

    fig.suptitle(
        "Delta = 0.000",
        x=0.07, y=0.96, ha="left", color=FG, fontsize=34, fontweight="bold",
    )
    ax.text(
        0.07, 0.875,
        "Base vs fine-tuned Gemma 4 on canine dermatology narrative diagnosis",
        transform=fig.transFigure, color=MUTED, fontsize=13, ha="left",
    )

    leg = ax.legend(
        loc="lower left", frameon=False, fontsize=11,
        labelcolor=FG, handlelength=1.5,
    )

    fig.text(
        0.07, 0.04,
        "n = 120 · seed 42 · Wilson 95% CIs · keywords fixed",
        color=MUTED, fontsize=10,
    )
    fig.text(
        0.93, 0.04,
        "Howl Vision · Gemma 4 Good Hackathon 2026",
        color=MUTED, fontsize=10, ha="right",
    )

    plt.subplots_adjust(left=0.07, right=0.97, top=0.82, bottom=0.13)
    fig.savefig(out_path, dpi=180, facecolor=BG, bbox_inches="tight", pad_inches=0.3)
    plt.close(fig)


def plot_identity_scatter(out_path: Path) -> None:
    items = sorted(
        DATA["base"]["per_class"].items(),
        key=lambda kv: -kv[1]["f1"],
    )
    names = [CLASS_LABELS[k] for k, _ in items]
    base_f1 = np.array([v["f1"] for _, v in items])
    ft_f1 = np.array([DATA["narrative"]["per_class"][k]["f1"] for k, _ in items])

    fig, ax = plt.subplots(figsize=(11, 6.75), facecolor=BG)
    setup_dark(ax)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)

    ax.plot([0, 1], [0, 1], color=MUTED, linewidth=1, linestyle="--", alpha=0.6, label="y = x")
    ax.scatter(base_f1, ft_f1, s=320, color=ACCENT_BASE, edgecolor=BG,
               linewidth=2.5, alpha=0.95, zorder=3)

    offsets = {
        "Demodicosis": (14, -4),
        "Dermatitis": (14, 10),
        "Flea allergy": (14, -4),
        "Healthy": (14, -4),
        "Ringworm": (14, 10),
        "Hypersensitivity": (-14, -16),
        "Scabies": (14, -4),
        "Fungal": (14, -4),
    }
    for nm, xv, yv in zip(names, base_f1, ft_f1):
        ox, oy = offsets.get(nm, (12, 8))
        ha = "left" if ox >= 0 else "right"
        ax.annotate(nm, (xv, yv), xytext=(ox, oy), textcoords="offset points",
                    color=FG, fontsize=11, ha=ha)

    ax.set_xlim(0.6, 1.04)
    ax.set_ylim(0.6, 1.04)
    ax.set_xlabel("F1 — Base Gemma 4", color=FG, fontsize=12, labelpad=10)
    ax.set_ylabel("F1 — Fine-tuned LoRA", color=FG, fontsize=12, labelpad=10)

    fig.suptitle(
        "Three days of fine-tuning. Zero movement off the diagonal.",
        x=0.06, y=0.95, ha="left", color=FG, fontsize=22, fontweight="bold",
    )
    ax.text(
        0.06, 0.875,
        "Per-class F1, base vs fine-tuned Gemma 4 — canine dermatology",
        transform=fig.transFigure, color=MUTED, fontsize=13, ha="left",
    )

    fig.text(
        0.06, 0.04,
        "n = 120 · seed 42 · 8 classes · all points on y = x",
        color=MUTED, fontsize=10,
    )
    fig.text(
        0.94, 0.04,
        "Howl Vision · Gemma 4 Good Hackathon 2026",
        color=MUTED, fontsize=10, ha="right",
    )

    plt.subplots_adjust(left=0.08, right=0.97, top=0.83, bottom=0.13)
    fig.savefig(out_path, dpi=180, facecolor=BG, bbox_inches="tight", pad_inches=0.3)
    plt.close(fig)


if __name__ == "__main__":
    out_bars = ROOT / "linkedin_delta_zero_bars.png"
    out_scatter = ROOT / "linkedin_delta_zero_scatter.png"
    plot_grouped_bars(out_bars)
    plot_identity_scatter(out_scatter)
    print(f"Generated: {out_bars}")
    print(f"Generated: {out_scatter}")
