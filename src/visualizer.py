"""
2D 시각화 모듈
- Zone별 월간 가동률 바 차트
- 설비 배치 2D 평면도 (Gantt 스타일 타임라인 포함)
- 시나리오 비교 차트
"""
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import matplotlib.ticker as mticker
from pathlib import Path
from datetime import date
import random

from src.data_loader import FactoryZone, Order
from src.space_calculator import MonthlyUsage
from src.layout_engine import LayoutScenario, PlacedEquipment

matplotlib.rcParams["font.family"] = ["Malgun Gothic", "AppleGothic", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False

OUTPUT_DIR = Path(__file__).parent.parent / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

# 설비 타입별 색상
TYPE_COLORS = {
    "저온": "#4A90D9",
    "고온": "#E05C5C",
    "RC":   "#5CB85C",
}
PRIORITY_EDGE = {"High": "#FF4444", "Medium": "#FF9900", "Low": "#888888"}


# ── 1. 월별 가동률 바 차트 ───────────────────────────────
def plot_monthly_utilization(
    monthly_usage: dict[str, list[MonthlyUsage]],
    save: bool = True,
) -> Path:
    zone_ids = sorted(monthly_usage.keys())
    n_zones  = len(zone_ids)

    fig, axes = plt.subplots(n_zones, 1, figsize=(14, 3.5 * n_zones), sharex=False)
    if n_zones == 1:
        axes = [axes]

    for ax, zone_id in zip(axes, zone_ids):
        usages = monthly_usage[zone_id]
        labels = [u.label for u in usages]
        utils  = [u.utilization * 100 for u in usages]
        colors = []
        for u in usages:
            if u.is_overloaded:
                colors.append("#E05C5C")
            elif u.utilization > 0.85:
                colors.append("#FF9900")
            else:
                colors.append("#4A90D9")

        bars = ax.bar(labels, utils, color=colors, edgecolor="white", linewidth=0.8)
        ax.axhline(100, color="red",    linestyle="--", linewidth=1.2, label="한계(100%)")
        ax.axhline(85,  color="orange", linestyle=":",  linewidth=1.0, label="주의(85%)")

        for bar, val in zip(bars, utils):
            ax.text(
                bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.5,
                f"{val:.0f}%", ha="center", va="bottom", fontsize=8
            )

        ax.set_title(f"{zone_id} — 월별 면적 가동률", fontsize=12, fontweight="bold", pad=8)
        ax.set_ylabel("가동률 (%)")
        ax.set_ylim(0, max(120, max(utils) + 15))
        ax.legend(loc="upper right", fontsize=8)
        ax.grid(axis="y", alpha=0.3)
        plt.setp(ax.get_xticklabels(), rotation=30, ha="right")

    fig.suptitle("공장 Zone별 월간 면적 가동률", fontsize=15, fontweight="bold", y=1.01)
    fig.tight_layout()

    out = OUTPUT_DIR / "monthly_utilization.png"
    if save:
        fig.savefig(out, dpi=150, bbox_inches="tight")
        print(f"[저장] {out}")
    plt.close(fig)
    return out


# ── 2. 2D 레이아웃 평면도 ────────────────────────────────
def plot_layout_2d(
    scenario: LayoutScenario,
    title_suffix: str = "",
    save: bool = True,
) -> Path:
    zone = scenario.zone
    fig, ax = plt.subplots(figsize=(14, 9))

    # Zone 외곽
    ax.set_xlim(-0.5, zone.width_m + 0.5)
    ax.set_ylim(-0.5, zone.depth_m + 0.5)
    ax.set_aspect("equal")

    zone_rect = mpatches.Rectangle(
        (0, 0), zone.width_m, zone.depth_m,
        linewidth=2, edgecolor="#333333", facecolor="#F5F5F5"
    )
    ax.add_patch(zone_rect)

    # 배치된 설비
    for p in scenario.placed:
        eq_type = p.order.eq_type
        color   = TYPE_COLORS.get(eq_type, "#AAAAAA")
        edge    = PRIORITY_EDGE.get(p.order.priority, "#555555")

        rect = FancyBboxPatch(
            (p.x, p.y), p.w, p.d,
            boxstyle="round,pad=0.05",
            linewidth=1.8, edgecolor=edge, facecolor=color, alpha=0.75
        )
        ax.add_patch(rect)

        # 설비 코드 + 프로젝트 ID 라벨
        cx, cy = p.x + p.w / 2, p.y + p.d / 2
        ax.text(cx, cy + 0.15, p.order.eq_code,
                ha="center", va="center", fontsize=7, fontweight="bold", color="white")
        ax.text(cx, cy - 0.2, p.order.project_id[-7:],
                ha="center", va="center", fontsize=6, color="white", alpha=0.9)

    # 미배치 설비 목록 표시
    if scenario.unplaced:
        unplaced_text = "미배치: " + ", ".join(o.project_id for o in scenario.unplaced)
        ax.text(0.01, -0.35, unplaced_text, transform=ax.transAxes,
                fontsize=7, color="red", va="top")

    # 범례
    legend_handles = [
        mpatches.Patch(color=c, label=t, alpha=0.75)
        for t, c in TYPE_COLORS.items()
    ]
    legend_handles += [
        mpatches.Patch(edgecolor=c, facecolor="none", linewidth=2,
                        label=f"우선순위: {p}")
        for p, c in PRIORITY_EDGE.items()
    ]
    ax.legend(handles=legend_handles, loc="upper right", fontsize=8,
              framealpha=0.9, ncol=2)

    ax.set_xlabel("폭 (m)", fontsize=10)
    ax.set_ylabel("깊이 (m)", fontsize=10)
    ax.xaxis.set_major_locator(mticker.MultipleLocator(5))
    ax.yaxis.set_major_locator(mticker.MultipleLocator(5))
    ax.grid(True, alpha=0.25, linestyle="--")

    title = (f"[{zone.zone_id}] 2D 레이아웃 — {scenario.name}"
             + (f"  ({title_suffix})" if title_suffix else ""))
    ax.set_title(title, fontsize=13, fontweight="bold", pad=10)

    stats = (f"배치: {len(scenario.placed)}대  |  "
             f"미배치: {len(scenario.unplaced)}대  |  "
             f"가동률: {scenario.utilization*100:.1f}%  |  "
             f"Zone 크기: {zone.width_m}×{zone.depth_m} m")
    fig.text(0.5, 0.01, stats, ha="center", fontsize=9, color="#555555")
    fig.tight_layout(rect=[0, 0.03, 1, 1])

    fname = f"layout_2d_{scenario.zone_id}_{scenario.name[:5].replace(' ','_')}.png"
    out = OUTPUT_DIR / fname
    if save:
        fig.savefig(out, dpi=150, bbox_inches="tight")
        print(f"[저장] {out}")
    plt.close(fig)
    return out


# ── 3. 제작 Gantt 타임라인 ───────────────────────────────
def plot_gantt(
    orders: list[Order],
    zone_filter: str = None,
    save: bool = True,
) -> Path:
    filtered = orders if not zone_filter else [o for o in orders if o.assigned_zone == zone_filter]
    if not filtered:
        print(f"[경고] {zone_filter} Zone에 수주 데이터 없음")
        return None

    filtered = sorted(filtered, key=lambda o: o.mfg_start)
    min_date = min(o.mfg_start for o in filtered)
    max_date = max(o.fob_date  for o in filtered)
    total_days = (max_date - min_date).days + 1

    fig, ax = plt.subplots(figsize=(16, max(6, len(filtered) * 0.5 + 2)))

    for i, order in enumerate(filtered):
        start_offset = (order.mfg_start - min_date).days
        duration     = order.duration_days
        color        = TYPE_COLORS.get(order.eq_type, "#AAAAAA")
        edge         = PRIORITY_EDGE.get(order.priority, "#555555")
        alpha        = 0.9 if order.delivery_type == "표준납기" else 0.6

        bar = ax.barh(
            i, duration, left=start_offset,
            color=color, edgecolor=edge, linewidth=1.5,
            alpha=alpha, height=0.7
        )

        # 단납기/FOB지연 표시
        if order.is_abnormal:
            marker = "⚡" if order.delivery_type == "단납기" else "⏰"
            ax.text(start_offset + duration / 2, i, marker,
                    ha="center", va="center", fontsize=9)

        label = f"{order.project_id[-7:]} [{order.eq_code}]"
        ax.text(start_offset - 0.5, i, label,
                ha="right", va="center", fontsize=7, color="#333333")

    # X축: 날짜 레이블 (30일 간격)
    tick_positions = list(range(0, total_days, 30))
    tick_labels = [(min_date.replace(day=1) if i == 0 else
                    date.fromordinal(min_date.toordinal() + t)).strftime("%Y-%m")
                   for t in tick_positions]
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels, rotation=30, ha="right", fontsize=8)

    ax.set_yticks([])
    ax.set_xlim(-12, total_days + 5)
    ax.set_ylim(-0.5, len(filtered) - 0.3)
    ax.invert_yaxis()

    ax.axvline(x=0, color="gray", linestyle="--", alpha=0.5)
    ax.grid(axis="x", alpha=0.25, linestyle="--")

    legend_handles  = [mpatches.Patch(color=c, label=t) for t, c in TYPE_COLORS.items()]
    legend_handles += [
        mpatches.Patch(facecolor="white", edgecolor="#555", label="표준납기 (불투명)"),
        mpatches.Patch(facecolor="gray",  edgecolor="#555", label="단납기/FOB지연 (반투명)", alpha=0.5),
    ]
    ax.legend(handles=legend_handles, loc="lower right", fontsize=8)

    zone_label = zone_filter or "전체"
    ax.set_title(f"[{zone_label}] 설비 제작 Gantt 타임라인", fontsize=13, fontweight="bold")
    ax.set_xlabel("제작 기간 (일 기준, 시작일 offset)")
    fig.tight_layout()

    fname = f"gantt_{zone_filter or 'ALL'}.png"
    out = OUTPUT_DIR / fname
    if save:
        fig.savefig(out, dpi=150, bbox_inches="tight")
        print(f"[저장] {out}")
    plt.close(fig)
    return out


# ── 4. 시나리오 비교 레이더 차트 ────────────────────────
def plot_scenario_comparison(scenarios: list[LayoutScenario], save: bool = True) -> Path:
    import numpy as np

    labels = ["배치율", "공간효율", "미배치\n(역산)", "점수\n(역산)"]
    n = len(labels)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))

    max_score = max(s.score for s in scenarios) or 1

    colors = ["#4A90D9", "#E05C5C", "#5CB85C", "#FF9900"]
    for idx, (scenario, color) in enumerate(zip(scenarios, colors)):
        placed_ratio   = len(scenario.placed) / max(len(scenario.placed) + len(scenario.unplaced), 1)
        space_eff      = scenario.space_efficiency
        unplaced_inv   = 1 - len(scenario.unplaced) / max(len(scenario.placed) + len(scenario.unplaced), 1)
        score_inv      = 1 - scenario.score / (max_score * 1.2)

        values = [placed_ratio, space_eff, unplaced_inv, max(0, score_inv)]
        values += values[:1]

        ax.plot(angles, values, color=color, linewidth=2, label=scenario.name)
        ax.fill(angles, values, color=color, alpha=0.18)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, fontsize=11)
    ax.set_ylim(0, 1)
    ax.set_yticks([0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(["25%", "50%", "75%", "100%"], fontsize=8)
    ax.legend(loc="upper right", bbox_to_anchor=(1.35, 1.1), fontsize=9)
    ax.set_title("시나리오 비교 — 레이더 차트", fontsize=13, fontweight="bold", pad=20)
    fig.tight_layout()

    out = OUTPUT_DIR / "scenario_comparison_radar.png"
    if save:
        fig.savefig(out, dpi=150, bbox_inches="tight")
        print(f"[저장] {out}")
    plt.close(fig)
    return out
