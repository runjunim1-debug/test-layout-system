"""
면적 계산 모듈
- 월별 Zone 점유 면적 계산
- 공간 부족 감지 및 필요 추가 면적 산출
- 가동률 / 여유율 지표 계산
"""
from datetime import date, timedelta
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from src.data_loader import FactoryZone, Order


@dataclass
class MonthlyUsage:
    year:           int
    month:          int
    zone_id:        str
    total_area:     float          # Zone 총 면적
    unusable_area:  float          # 불용 면적
    usable_area:    float          # 사용 가능 면적
    occupied_area:  float          # 실제 점유 면적 (설비 작업 면적 합계)
    free_area:      float          # 여유 면적
    utilization:    float          # 가동률 (occupied / usable)
    orders:         list = field(default_factory=list)   # 해당 월 활성 수주 목록

    @property
    def is_overloaded(self) -> bool:
        return self.occupied_area > self.usable_area

    @property
    def shortage_area(self) -> float:
        """공간 부족 시 추가 필요 면적 (양수면 부족)"""
        return max(0.0, self.occupied_area - self.usable_area)

    @property
    def label(self) -> str:
        return f"{self.year}-{self.month:02d}"


def _first_day(year: int, month: int) -> date:
    return date(year, month, 1)


def _last_day(year: int, month: int) -> date:
    if month == 12:
        return date(year + 1, 1, 1) - timedelta(days=1)
    return date(year, month + 1, 1) - timedelta(days=1)


def _date_range_months(start: date, end: date) -> list[tuple[int, int]]:
    """start ~ end 사이의 (year, month) 목록 반환"""
    months = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        months.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return months


def calculate_monthly_usage(
    zones: dict[str, FactoryZone],
    orders: list[Order],
    target_months: Optional[list[tuple[int, int]]] = None,
) -> dict[str, list[MonthlyUsage]]:
    """
    Zone별 월별 점유 면적을 계산합니다.

    Returns
    -------
    dict: {zone_id -> [MonthlyUsage, ...]} (월 오름차순)
    """
    if not orders:
        return {}

    # 분석 기간 자동 설정
    if target_months is None:
        all_starts = [o.mfg_start for o in orders]
        all_ends   = [o.fob_date  for o in orders]
        target_months = _date_range_months(min(all_starts), max(all_ends))

    # zone_id별로 월별 집계
    result: dict[str, list[MonthlyUsage]] = defaultdict(list)

    for zone_id, zone in zones.items():
        for (year, month) in target_months:
            month_start = _first_day(year, month)
            month_end   = _last_day(year, month)

            # 이 달에 활성 상태인 수주 필터링 (해당 Zone)
            active_orders = [
                o for o in orders
                if o.assigned_zone == zone_id
                and o.mfg_start <= month_end
                and o.fob_date  >= month_start
            ]

            occupied = sum(o.area_sqm for o in active_orders)
            free     = zone.usable_area - occupied

            result[zone_id].append(MonthlyUsage(
                year          = year,
                month         = month,
                zone_id       = zone_id,
                total_area    = zone.total_area,
                unusable_area = zone.unusable_area,
                usable_area   = zone.usable_area,
                occupied_area = occupied,
                free_area     = free,
                utilization   = occupied / zone.usable_area if zone.usable_area > 0 else 0,
                orders        = active_orders,
            ))

    return dict(result)


def find_overload_periods(
    monthly_usage: dict[str, list[MonthlyUsage]]
) -> list[MonthlyUsage]:
    """공간 초과(가동률 > 100%) 구간 목록 반환"""
    overloads = []
    for zone_usages in monthly_usage.values():
        for mu in zone_usages:
            if mu.is_overloaded:
                overloads.append(mu)
    return sorted(overloads, key=lambda x: (x.label, x.zone_id))


def suggest_reallocation(
    overloaded: MonthlyUsage,
    zones: dict[str, FactoryZone],
    monthly_usage: dict[str, list[MonthlyUsage]],
) -> list[dict]:
    """
    공간 초과 구간에서 대안 Zone을 추천합니다.
    여유 면적이 부족량 이상인 Zone 목록을 반환.
    """
    year, month = overloaded.year, overloaded.month
    shortage    = overloaded.shortage_area
    suggestions = []

    for zone_id, usages in monthly_usage.items():
        if zone_id == overloaded.zone_id:
            continue
        # 같은 달 데이터 찾기
        same_month = [u for u in usages if u.year == year and u.month == month]
        if not same_month:
            continue
        mu = same_month[0]
        if mu.free_area >= shortage:
            suggestions.append({
                "zone_id":    zone_id,
                "zone_name":  zones[zone_id].name,
                "free_area":  round(mu.free_area, 2),
                "shortage":   round(shortage, 2),
                "margin":     round(mu.free_area - shortage, 2),
                "utilization": round(mu.utilization * 100, 1),
            })

    return sorted(suggestions, key=lambda x: -x["free_area"])


def print_summary(monthly_usage: dict[str, list[MonthlyUsage]], zones: dict[str, FactoryZone]):
    """콘솔 요약 출력"""
    print("\n" + "="*72)
    print("  Zone별 월간 면적 가동률 요약")
    print("="*72)
    print(f"{'Zone':<12} {'월':<10} {'가용(㎡)':>8} {'점유(㎡)':>8} {'여유(㎡)':>8} {'가동률':>7} {'상태':>6}")
    print("-"*72)
    for zone_id in sorted(monthly_usage.keys()):
        for mu in monthly_usage[zone_id]:
            status = "⚠ 초과" if mu.is_overloaded else ("△ 주의" if mu.utilization > 0.85 else "  양호")
            print(
                f"{zone_id:<12} {mu.label:<10} "
                f"{mu.usable_area:>8.1f} {mu.occupied_area:>8.1f} "
                f"{mu.free_area:>8.1f} {mu.utilization*100:>6.1f}% {status:>6}"
            )
    print("="*72)
