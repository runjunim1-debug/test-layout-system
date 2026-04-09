# -*- coding: utf-8 -*-
"""
Plotly 기반 인터랙티브 차트 모듈
Streamlit 웹앱에서 사용
"""
from __future__ import annotations
from datetime import date
from typing import Optional

import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd

from src.data_loader import FactoryZone, Order, EquipmentSpec
from src.space_calculator import MonthlyUsage
from src.layout_engine import LayoutScenario

# ── 공통 색상 ────────────────────────────────────────────
TYPE_COLORS  = {"저온": "#4A90D9", "고온": "#E05C5C", "RC": "#5CB85C"}
PRIO_COLORS  = {"High": "#FF4444", "Medium": "#FF9900", "Low": "#AAAAAA"}
ZONE_PALETTE = {
    "F1-A": "#636EFA", "F1-B": "#EF553B",
    "F2":   "#00CC96", "OUTSOURCE": "#AB63FA",
}


# ── 1. 월별 가동률 바 차트 ───────────────────────────────
def fig_monthly_utilization(
    monthly_usage: dict[str, list[MonthlyUsage]],
    selected_zones: Optional[list[str]] = None,
) -> go.Figure:
    zones = [z for z in (selected_zones or sorted(monthly_usage.keys())) if z in monthly_usage]
    if not zones:
        return go.Figure()
    n = len(zones)
    fig = make_subplots(
        rows=n, cols=1,
        subplot_titles=[f"{z} — 월별 가동률" for z in zones],
        vertical_spacing=0.08,
    )

    for row_idx, zone_id in enumerate(zones, start=1):
        usages = monthly_usage.get(zone_id, [])
        labels = [u.label for u in usages]
        utils  = [round(u.utilization * 100, 1) for u in usages]
        colors = []
        for u in usages:
            if u.is_overloaded:
                colors.append("#E05C5C")
            elif u.utilization > 0.85:
                colors.append("#FF9900")
            else:
                colors.append(ZONE_PALETTE.get(zone_id, "#4A90D9"))

        hover = [
            f"<b>{u.label}</b><br>"
            f"가동률: {u.utilization*100:.1f}%<br>"
            f"점유: {u.occupied_area:.1f} sqm<br>"
            f"가용: {u.usable_area:.1f} sqm<br>"
            f"여유: {u.free_area:.1f} sqm<br>"
            f"활성 수주: {len(u.orders)}건"
            for u in usages
        ]

        fig.add_trace(
            go.Bar(
                x=labels, y=utils,
                marker_color=colors,
                text=[f"{v}%" for v in utils],
                textposition="outside",
                hovertext=hover,
                hoverinfo="text",
                name=zone_id,
                showlegend=(row_idx == 1),
            ),
            row=row_idx, col=1,
        )
        # 한계선
        fig.add_hline(y=100, line_dash="dash", line_color="red",
                      annotation_text="한계(100%)", row=row_idx, col=1)
        fig.add_hline(y=85, line_dash="dot", line_color="orange",
                      annotation_text="주의(85%)", row=row_idx, col=1)

    fig.update_layout(
        height=320 * n,
        title_text="공장 Zone별 월간 면적 가동률",
        title_font_size=18,
        plot_bgcolor="white",
        paper_bgcolor="#FAFAFA",
        showlegend=False,
    )
    fig.update_yaxes(range=[0, 130], ticksuffix="%")
    return fig


# ── 2. 2D 레이아웃 평면도 ────────────────────────────────
def fig_layout_2d(scenario: LayoutScenario) -> go.Figure:
    zone = scenario.zone
    fig  = go.Figure()

    # Zone 외곽선
    fig.add_shape(
        type="rect", x0=0, y0=0, x1=zone.width_m, y1=zone.depth_m,
        line=dict(color="#333333", width=2),
        fillcolor="#F8F8F8",
        layer="below",
    )

    # 배치된 설비
    for p in scenario.placed:
        color    = TYPE_COLORS.get(p.order.eq_type, "#AAAAAA")
        border   = PRIO_COLORS.get(p.order.priority, "#555555")
        cx, cy   = p.x + p.w / 2, p.y + p.d / 2

        fig.add_shape(
            type="rect",
            x0=p.x, y0=p.y, x1=p.x + p.w, y1=p.y + p.d,
            line=dict(color=border, width=2),
            fillcolor=color,
            opacity=0.75,
        )
        hover_txt = (
            f"<b>{p.order.project_id}</b><br>"
            f"코드: {p.order.eq_code}<br>"
            f"타입: {p.order.eq_type} / {p.order.generation}<br>"
            f"구성: {p.order.config}<br>"
            f"고객: {p.order.customer}<br>"
            f"납기: {p.order.delivery_type}<br>"
            f"제작: {p.order.mfg_start} ~ {p.order.fob_date}<br>"
            f"면적: {p.w:.1f} x {p.d:.1f} m = {p.area:.1f} sqm<br>"
            f"우선순위: {p.order.priority}"
        )
        fig.add_trace(go.Scatter(
            x=[cx], y=[cy],
            mode="text+markers",
            text=[f"{p.order.eq_code}<br><sub>{p.order.project_id[-7:]}</sub>"],
            textfont=dict(size=9, color="white"),
            marker=dict(opacity=0, size=1),
            hovertext=[hover_txt],
            hoverinfo="text",
            showlegend=False,
        ))

    # 미배치 설비 안내
    if scenario.unplaced:
        unplaced_ids = ", ".join(o.project_id for o in scenario.unplaced)
        fig.add_annotation(
            x=0, y=-1.5, xref="x", yref="y",
            text=f"미배치: {unplaced_ids}",
            showarrow=False, font=dict(size=10, color="red"), xanchor="left",
        )

    # 범례용 더미 트레이스
    for eq_type, color in TYPE_COLORS.items():
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode="markers",
            marker=dict(size=12, color=color),
            name=eq_type, showlegend=True,
        ))
    for prio, color in PRIO_COLORS.items():
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode="markers",
            marker=dict(size=10, color="white",
                        line=dict(color=color, width=2.5)),
            name=f"우선순위: {prio}", showlegend=True,
        ))

    fig.update_layout(
        title=dict(
            text=(f"[{zone.zone_id}] 2D 레이아웃 — {scenario.name}<br>"
                  f"<sup>배치 {len(scenario.placed)}대 | "
                  f"미배치 {len(scenario.unplaced)}대 | "
                  f"가동률 {scenario.utilization*100:.1f}%</sup>"),
            font_size=15,
        ),
        xaxis=dict(title="폭 (m)", range=[-0.5, zone.width_m + 0.5],
                   gridcolor="#E0E0E0", dtick=5),
        yaxis=dict(title="깊이 (m)", range=[-2.5, zone.depth_m + 0.5],
                   gridcolor="#E0E0E0", dtick=5, scaleanchor="x", scaleratio=1),
        height=600,
        plot_bgcolor="white",
        paper_bgcolor="#FAFAFA",
        legend=dict(orientation="v", x=1.02, y=1),
        margin=dict(r=160),
    )
    return fig


# ── 3. Gantt 타임라인 ────────────────────────────────────
def fig_gantt(
    orders: list[Order],
    zone_filter: Optional[str] = None,
) -> go.Figure:
    filtered = orders if not zone_filter else [o for o in orders if o.assigned_zone == zone_filter]
    if not filtered:
        return go.Figure()

    rows = []
    for o in filtered:
        rows.append({
            "project_id":    o.project_id,
            "label":         f"{o.project_id} [{o.eq_code}]",
            "eq_type":       o.eq_type,
            "customer":      o.customer,
            "delivery_type": o.delivery_type,
            "priority":      o.priority,
            "zone":          o.assigned_zone,
            "start":         pd.Timestamp(o.mfg_start),
            "finish":        pd.Timestamp(o.fob_date),
            "color":         TYPE_COLORS.get(o.eq_type, "#AAAAAA"),
        })
    df = pd.DataFrame(rows).sort_values("start")

    fig = px.timeline(
        df,
        x_start="start", x_end="finish",
        y="label",
        color="eq_type",
        color_discrete_map=TYPE_COLORS,
        hover_data=["customer", "delivery_type", "priority", "zone"],
        labels={"eq_type": "설비 타입", "label": ""},
    )
    fig.update_yaxes(autorange="reversed")

    # 단납기 / FOB지연 마커
    for _, row in df.iterrows():
        o = next(x for x in filtered if x.project_id == row["project_id"])
        if o.delivery_type == "단납기":
            mid = row["start"] + (row["finish"] - row["start"]) / 2
            fig.add_trace(go.Scatter(
                x=[mid], y=[row["label"]],
                mode="text", text=["⚡"],
                textfont=dict(size=14), showlegend=False, hoverinfo="skip",
            ))
        elif o.delivery_type == "FOB지연":
            mid = row["start"] + (row["finish"] - row["start"]) / 2
            fig.add_trace(go.Scatter(
                x=[mid], y=[row["label"]],
                mode="text", text=["⏰"],
                textfont=dict(size=14), showlegend=False, hoverinfo="skip",
            ))

    zone_label = zone_filter or "전체"
    fig.update_layout(
        title=f"[{zone_label}] 설비 제작 Gantt 타임라인",
        title_font_size=16,
        height=max(450, len(filtered) * 28 + 120),
        plot_bgcolor="white",
        paper_bgcolor="#FAFAFA",
        xaxis_title="제작 기간",
        legend_title="설비 타입",
    )
    return fig


# ── 4. 시나리오 비교 레이더 차트 ────────────────────────
def fig_radar(scenarios: list[LayoutScenario]) -> go.Figure:
    categories = ["배치율", "공간효율", "미배치(역산)", "점수(역산)"]
    max_score  = max(s.score for s in scenarios) or 1
    colors     = ["#4A90D9", "#E05C5C", "#5CB85C", "#FF9900"]

    fig = go.Figure()
    for s, color in zip(scenarios, colors):
        total         = len(s.placed) + len(s.unplaced) or 1
        placed_ratio  = len(s.placed) / total
        space_eff     = s.space_efficiency
        unplaced_inv  = 1 - len(s.unplaced) / total
        score_inv     = max(0, 1 - s.score / (max_score * 1.2))

        vals = [placed_ratio, space_eff, unplaced_inv, score_inv]
        vals_pct = [round(v * 100, 1) for v in vals]

        fig.add_trace(go.Scatterpolar(
            r=vals_pct + [vals_pct[0]],
            theta=categories + [categories[0]],
            fill="toself",
            fillcolor=color,
            opacity=0.25,
            line=dict(color=color, width=2),
            name=s.name,
            hovertemplate=(
                f"<b>{s.name}</b><br>"
                f"배치: {len(s.placed)}대 / 미배치: {len(s.unplaced)}대<br>"
                f"가동률: {s.utilization*100:.1f}%<br>"
                f"점수: {s.score:.1f}"
                "<extra></extra>"
            ),
        ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 100], ticksuffix="%"),
        ),
        title="시나리오 비교 — 레이더 차트",
        title_font_size=16,
        height=480,
        paper_bgcolor="#FAFAFA",
        legend=dict(orientation="h", y=-0.15),
    )
    return fig


# ── 5. Zone 별 가용 면적 파이 차트 ──────────────────────
def fig_zone_area_pie(zones: dict[str, FactoryZone]) -> go.Figure:
    labels = list(zones.keys())
    usable = [z.usable_area for z in zones.values()]
    unusable = [z.unusable_area for z in zones.values()]

    fig = make_subplots(
        rows=1, cols=2,
        specs=[[{"type": "pie"}, {"type": "pie"}]],
        subplot_titles=["가용 면적 비율", "불용 면적 비율"],
    )
    fig.add_trace(go.Pie(
        labels=labels, values=usable,
        marker_colors=[ZONE_PALETTE.get(z, "#999") for z in labels],
        hole=0.4, name="가용",
        hovertemplate="%{label}: %{value} sqm<extra></extra>",
    ), row=1, col=1)
    fig.add_trace(go.Pie(
        labels=labels, values=unusable,
        marker_colors=[ZONE_PALETTE.get(z, "#999") for z in labels],
        hole=0.4, name="불용",
        hovertemplate="%{label}: %{value} sqm<extra></extra>",
    ), row=1, col=2)

    fig.update_layout(
        title="Zone별 면적 구성",
        title_font_size=16,
        height=380,
        paper_bgcolor="#FAFAFA",
    )
    return fig


# ── 6. 수주 현황 테이블용 DataFrame ─────────────────────
def orders_to_df(orders: list[Order]) -> pd.DataFrame:
    return pd.DataFrame([{
        "프로젝트 ID":  o.project_id,
        "고객사":       o.customer,
        "지역":         o.region,
        "설비 타입":    o.eq_type,
        "세대":         o.generation,
        "구성":         o.config,
        "코드":         o.eq_code,
        "면적(sqm)":   round(o.area_sqm, 2),
        "납기 구분":    o.delivery_type,
        "리드타임(일)": o.lead_days,
        "제작 시작":    o.mfg_start.strftime("%Y-%m-%d"),
        "FOB":          o.fob_date.strftime("%Y-%m-%d"),
        "배치 Zone":    o.assigned_zone,
        "상태":         o.status,
        "우선순위":     o.priority,
    } for o in orders])
