# -*- coding: utf-8 -*-
"""
설비 Layout 배치 시스템 -- 파일럿
실행: python main.py
"""
import sys
import io

# Windows 터미널 UTF-8 출력 강제
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from src.data_loader import load_all
from src.space_calculator import (
    calculate_monthly_usage,
    find_overload_periods,
    suggest_reallocation,
    print_summary,
)
from src.layout_engine import generate_scenarios, pick_best, compare_scenarios
from src.visualizer import (
    plot_monthly_utilization,
    plot_layout_2d,
    plot_gantt,
    plot_scenario_comparison,
)


def main():
    print("\n" + "="*60)
    print("  설비 Layout 배치 시스템 -- 파일럿 테스트")
    print("="*60)

    # STEP 1. 데이터 로드
    print("\n[STEP 1] 데이터 로드 중...")
    zones, specs, orders = load_all()
    print(f"  공장 Zone : {len(zones)}개  {list(zones.keys())}")
    print(f"  설비 스펙 : {len(specs)}종")
    print(f"  수주 건수 : {len(orders)}건 ({orders[0].mfg_start} ~ {orders[-1].fob_date})")

    # STEP 2. 월별 면적 가동률 계산
    print("\n[STEP 2] 월별 Zone 가동률 계산 중...")
    monthly = calculate_monthly_usage(zones, orders)
    print_summary(monthly, zones)

    overloads = find_overload_periods(monthly)
    if overloads:
        print(f"\n[경고] 공간 초과 구간 {len(overloads)}건 감지:")
        for ol in overloads:
            print(f"  [{ol.zone_id}] {ol.label}  "
                  f"점유:{ol.occupied_area:.1f}sqm / 가용:{ol.usable_area:.1f}sqm  "
                  f"부족:{ol.shortage_area:.1f}sqm")
            suggestions = suggest_reallocation(ol, zones, monthly)
            if suggestions:
                best_alt = suggestions[0]
                print(f"  -> 대안 Zone 추천: {best_alt['zone_name']} "
                      f"(여유 {best_alt['free_area']}sqm, 여유분 {best_alt['margin']}sqm)")
    else:
        print("\n[OK] 공간 초과 구간 없음 -- 모든 Zone 정상 범위")

    # STEP 3. 2D 레이아웃 배치 & 시나리오 생성
    print("\n[STEP 3] 레이아웃 시나리오 생성 중...")
    target_zone_id = "F1-A"
    zone_orders    = [o for o in orders if o.assigned_zone == target_zone_id]
    print(f"  대상 Zone: {target_zone_id}  수주 {len(zone_orders)}건")

    scenarios = generate_scenarios(zones[target_zone_id], zone_orders, specs)
    compare_scenarios(scenarios)
    best = pick_best(scenarios)

    # STEP 4. 시각화 출력
    print("\n[STEP 4] 차트 및 레이아웃 이미지 생성 중...")
    plot_monthly_utilization(monthly)
    plot_gantt(orders, zone_filter=target_zone_id)
    plot_gantt(orders)
    plot_layout_2d(best, title_suffix="최적 추천")
    for s in scenarios:
        plot_layout_2d(s)
    plot_scenario_comparison(scenarios)

    # STEP 5. 최종 요약
    print("\n" + "="*60)
    print("  최종 분석 요약")
    print("="*60)
    print(f"  분석 기간  : {orders[0].mfg_start} ~ {orders[-1].fob_date}")
    print(f"  전체 수주  : {len(orders)}건  /  총 점유 면적: {sum(o.area_sqm for o in orders):.1f}sqm")
    print(f"  공간 초과  : {len(overloads)}건")
    print(f"  추천 시나리오 [{target_zone_id}]: {best.name}")
    print(f"    배치 {len(best.placed)}대  |  미배치 {len(best.unplaced)}대  |  "
          f"가동률 {best.utilization*100:.1f}%")
    print(f"\n  출력 파일 -> outputs/ 폴더 확인")
    print("="*60)


if __name__ == "__main__":
    main()
