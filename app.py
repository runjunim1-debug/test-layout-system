# -*- coding: utf-8 -*-
"""
설비 Layout 배치 시스템 — Streamlit 웹앱
실행: streamlit run app.py
"""
import streamlit as st
from datetime import date

from src.data_loader import load_all
from src.space_calculator import (
    calculate_monthly_usage,
    find_overload_periods,
    suggest_reallocation,
)
from src.layout_engine import generate_scenarios, pick_best
from src.charts import (
    fig_monthly_utilization,
    fig_layout_2d,
    fig_gantt,
    fig_radar,
    fig_zone_area_pie,
    orders_to_df,
)

# ── 페이지 기본 설정 ────────────────────────────────────
st.set_page_config(
    page_title="설비 Layout 배치 시스템",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 데이터 캐싱 ─────────────────────────────────────────
@st.cache_data
def get_data():
    return load_all()


# ── 사이드바 ─────────────────────────────────────────────
def render_sidebar(zones, orders):
    st.sidebar.title("🏭 설비 Layout 시스템")
    st.sidebar.markdown("---")

    st.sidebar.subheader("필터 설정")

    all_zone_ids = list(zones.keys())
    selected_zones = st.sidebar.multiselect(
        "공장 Zone 선택",
        options=all_zone_ids,
        default=all_zone_ids,
    )

    all_types = sorted(set(o.eq_type for o in orders))
    selected_types = st.sidebar.multiselect(
        "설비 타입",
        options=all_types,
        default=all_types,
    )

    delivery_opts = ["표준납기", "단납기", "FOB지연"]
    selected_delivery = st.sidebar.multiselect(
        "납기 구분",
        options=delivery_opts,
        default=delivery_opts,
    )

    st.sidebar.markdown("---")
    st.sidebar.subheader("레이아웃 설정")

    layout_zone = st.sidebar.selectbox(
        "배치 분석 Zone",
        options=all_zone_ids,
        index=0,
    )

    scenario_names = ["시나리오A: 납기일 순", "시나리오B: 우선순위 순", "시나리오C: 대형 설비 우선"]
    selected_scenario = st.sidebar.radio(
        "시나리오 선택",
        options=scenario_names,
        index=0,
    )

    st.sidebar.markdown("---")
    st.sidebar.caption("© 2025 AX 파일럿 프로젝트")

    return selected_zones, selected_types, selected_delivery, layout_zone, selected_scenario


# ── 탭 1: 대시보드 ───────────────────────────────────────
def tab_dashboard(zones, orders, monthly, selected_zones):
    st.header("📊 공장 운영 대시보드")

    # KPI 카드
    overloads = find_overload_periods(monthly)
    total_orders = len(orders)
    abnormal = sum(1 for o in orders if o.is_abnormal)
    total_area = sum(o.area_sqm for o in orders)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("전체 수주", f"{total_orders}건")
    c2.metric("비정상 납기", f"{abnormal}건",
              delta=f"{abnormal/total_orders*100:.0f}%" if total_orders else "0%",
              delta_color="inverse")
    c3.metric("총 점유 면적", f"{total_area:.0f} sqm")
    c4.metric("공간 초과 구간", f"{len(overloads)}건",
              delta="주의 필요" if overloads else "정상",
              delta_color="inverse" if overloads else "off")

    st.markdown("---")

    # 공간 초과 경고 배너
    if overloads:
        for ol in overloads:
            suggestions = suggest_reallocation(ol, zones, monthly)
            alt = f" → 대안: {suggestions[0]['zone_name']}" if suggestions else ""
            st.warning(
                f"⚠️ **[{ol.zone_id}] {ol.label}** — "
                f"점유 {ol.occupied_area:.0f} sqm / 가용 {ol.usable_area:.0f} sqm "
                f"(부족 {ol.shortage_area:.0f} sqm){alt}"
            )
    else:
        st.success("✅ 모든 Zone이 정상 범위입니다.")

    st.markdown("---")

    col_left, col_right = st.columns([2, 1])
    with col_left:
        st.subheader("월별 면적 가동률")
        st.plotly_chart(
            fig_monthly_utilization(monthly, selected_zones),
            use_container_width=True,
        )
    with col_right:
        st.subheader("Zone별 면적 구성")
        filtered_zones = {z: zones[z] for z in selected_zones if z in zones}
        st.plotly_chart(
            fig_zone_area_pie(filtered_zones),
            use_container_width=True,
        )

        st.subheader("Zone 면적 현황")
        zone_rows = []
        for zid in selected_zones:
            z = zones[zid]
            zone_rows.append({
                "Zone": zid,
                "총면적(sqm)": z.total_area,
                "불용(sqm)": z.unusable_area,
                "가용(sqm)": z.usable_area,
                "가용률": f"{z.efficiency_ratio*100:.0f}%",
            })
        import pandas as pd
        st.dataframe(pd.DataFrame(zone_rows), hide_index=True, use_container_width=True)


# ── 탭 2: 레이아웃 배치 ──────────────────────────────────
def tab_layout(zones, specs, orders, layout_zone, selected_scenario):
    st.header("📐 2D 레이아웃 배치")

    zone_orders = [o for o in orders if o.assigned_zone == layout_zone]
    if not zone_orders:
        st.info(f"{layout_zone} Zone에 배치된 수주가 없습니다.")
        return

    scenarios = generate_scenarios(zones[layout_zone], zone_orders, specs)
    best = pick_best(scenarios)

    # 선택된 시나리오 찾기
    scenario_map = {s.name: s for s in scenarios}
    current = scenario_map.get(selected_scenario, best)

    # 시나리오 KPI
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("배치 설비", f"{len(current.placed)}대")
    c2.metric("미배치 설비", f"{len(current.unplaced)}대",
              delta_color="inverse" if current.unplaced else "off",
              delta="재배치 필요" if current.unplaced else "없음")
    c3.metric("가동률", f"{current.utilization*100:.1f}%")
    c4.metric(
        "추천 시나리오",
        best.name[:5],
        delta="현재 선택" if current.name == best.name else "★ 최적 아님",
        delta_color="off" if current.name == best.name else "inverse",
    )

    st.markdown("---")

    col_chart, col_info = st.columns([3, 1])
    with col_chart:
        st.plotly_chart(fig_layout_2d(current), use_container_width=True)

    with col_info:
        st.subheader("시나리오 비교")
        st.plotly_chart(fig_radar(scenarios), use_container_width=True)

        if current.unplaced:
            st.error("**미배치 설비**")
            for o in current.unplaced:
                st.write(f"- {o.project_id} ({o.eq_code})")

    # 배치 설비 목록
    with st.expander("배치 설비 목록 상세"):
        import pandas as pd
        rows = [{
            "프로젝트": p.order.project_id,
            "코드": p.order.eq_code,
            "타입": p.order.eq_type,
            "X(m)": round(p.x, 1), "Y(m)": round(p.y, 1),
            "W(m)": round(p.w, 1), "D(m)": round(p.d, 1),
            "면적(sqm)": round(p.area, 1),
            "우선순위": p.order.priority,
            "납기": p.order.delivery_type,
        } for p in current.placed]
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


# ── 탭 3: Gantt 타임라인 ─────────────────────────────────
def tab_gantt(orders, selected_zones):
    st.header("📅 제작 Gantt 타임라인")

    view_mode = st.radio(
        "보기 방식",
        options=["전체", "Zone별"],
        horizontal=True,
    )

    if view_mode == "전체":
        st.plotly_chart(fig_gantt(orders), use_container_width=True, key="gantt_all")
    else:
        for zone_id in selected_zones:
            zone_orders = [o for o in orders if o.assigned_zone == zone_id]
            if zone_orders:
                st.plotly_chart(
                    fig_gantt(orders, zone_filter=zone_id),
                    use_container_width=True,
                    key=f"gantt_{zone_id}",
                )


# ── 탭 4: 수주 현황 ──────────────────────────────────────
def tab_orders(orders):
    st.header("📋 수주 현황")

    df = orders_to_df(orders)

    # 검색
    search = st.text_input("프로젝트 ID / 고객사 검색", placeholder="예: PJT-2025-001 또는 삼성전자")
    if search:
        mask = (
            df["프로젝트 ID"].str.contains(search, case=False, na=False) |
            df["고객사"].str.contains(search, case=False, na=False)
        )
        df = df[mask]

    # 집계 요약
    c1, c2, c3 = st.columns(3)
    c1.metric("표시 건수", f"{len(df)}건")
    c2.metric("표준납기", f"{(df['납기 구분']=='표준납기').sum()}건")
    c3.metric("비정상(단납기+FOB지연)", f"{(df['납기 구분']!='표준납기').sum()}건")

    # 색상 강조 함수
    def highlight_delivery(val):
        if val == "단납기":
            return "background-color: #FFF3CD; color: #856404"
        elif val == "FOB지연":
            return "background-color: #F8D7DA; color: #721C24"
        return ""

    st.dataframe(
        df.style.map(highlight_delivery, subset=["납기 구분"]),
        use_container_width=True,
        height=500,
    )

    # 다운로드
    csv = df.to_csv(index=False, encoding="utf-8-sig")
    st.download_button(
        label="📥 CSV 다운로드",
        data=csv.encode("utf-8-sig"),
        file_name="orders_export.csv",
        mime="text/csv",
    )


# ── 메인 ─────────────────────────────────────────────────
def main():
    zones, specs, orders = get_data()
    monthly = calculate_monthly_usage(zones, orders)

    selected_zones, selected_types, selected_delivery, layout_zone, selected_scenario = \
        render_sidebar(zones, orders)

    # 필터 적용
    filtered_orders = [
        o for o in orders
        if o.assigned_zone in selected_zones
        and o.eq_type in selected_types
        and o.delivery_type in selected_delivery
    ]
    filtered_monthly = calculate_monthly_usage(
        {z: zones[z] for z in selected_zones},
        filtered_orders,
    )

    # 탭 구성
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 대시보드",
        "📐 레이아웃 배치",
        "📅 Gantt 타임라인",
        "📋 수주 현황",
    ])

    with tab1:
        tab_dashboard(zones, filtered_orders, filtered_monthly, selected_zones)
    with tab2:
        tab_layout(zones, specs, filtered_orders, layout_zone, selected_scenario)
    with tab3:
        tab_gantt(filtered_orders, selected_zones)
    with tab4:
        tab_orders(filtered_orders)


if __name__ == "__main__":
    main()
