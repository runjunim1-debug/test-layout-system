"""
레이아웃 배치 엔진
- 설비를 Zone 내에 사각형으로 배치 (Bin Packing 기반)
- 멀티 시나리오 생성 (표준 / 단납기 / 우선순위 순)
- 시나리오 간 효율 지표 비교 및 최적안 추천
"""
import random
from dataclasses import dataclass, field
from typing import Optional
from src.data_loader import FactoryZone, EquipmentSpec, Order


# ── 배치 결과 단위 ────────────────────────────────────────
@dataclass
class PlacedEquipment:
    order:      Order
    spec:       Optional[EquipmentSpec]
    x:          float   # Zone 내 좌측 하단 x (m)
    y:          float   # Zone 내 좌측 하단 y (m)
    w:          float   # 배치 폭 (m)
    d:          float   # 배치 깊이 (m)
    rotated:    bool = False

    @property
    def area(self) -> float:
        return self.w * self.d


@dataclass
class LayoutScenario:
    name:       str
    zone_id:    str
    zone:       FactoryZone
    placed:     list[PlacedEquipment] = field(default_factory=list)
    unplaced:   list[Order]           = field(default_factory=list)

    @property
    def total_placed_area(self) -> float:
        return sum(p.area for p in self.placed)

    @property
    def utilization(self) -> float:
        if self.zone.usable_area <= 0:
            return 0
        return self.total_placed_area / self.zone.usable_area

    @property
    def space_efficiency(self) -> float:
        """배치된 설비 면적 / Zone 전체 면적 비율"""
        return self.total_placed_area / self.zone.total_area if self.zone.total_area > 0 else 0

    @property
    def score(self) -> float:
        """
        종합 점수 (낮을수록 좋음):
        - 미배치 설비 패널티
        - 가동률이 85~95% 구간을 최적으로 봄
        """
        unplaced_penalty = len(self.unplaced) * 50
        util = self.utilization
        if util < 0.5:
            util_score = (0.5 - util) * 30    # 너무 여유 있음
        elif util <= 0.92:
            util_score = 0                      # 최적 구간
        else:
            util_score = (util - 0.92) * 80   # 과밀 패널티
        return unplaced_penalty + util_score


# ── 내부 유틸: 겹침 검사 ──────────────────────────────────
def _overlaps(x1, y1, w1, d1, x2, y2, w2, d2, gap=0.3) -> bool:
    """두 사각형이 gap 이상 붙어 있는지 (통로 확보 포함)"""
    return not (
        x1 + w1 + gap <= x2 or x2 + w2 + gap <= x1 or
        y1 + d1 + gap <= y2 or y2 + d2 + gap <= y1
    )


def _find_position(
    zone: FactoryZone,
    w: float,
    d: float,
    placed: list[PlacedEquipment],
    aisle: float,
    grid_step: float = 0.5,
) -> Optional[tuple[float, float]]:
    """
    Zone 내에서 설비(w×d)를 배치할 수 있는 위치를 탐색합니다.
    좌하단부터 행 우선으로 스캔.
    """
    margin = aisle
    x_max = zone.width_m - w - margin
    y_max = zone.depth_m - d - margin

    if x_max < margin or y_max < margin:
        return None

    x = margin
    while x <= x_max:
        y = margin
        while y <= y_max:
            collision = any(
                _overlaps(x, y, w, d, p.x, p.y, p.w, p.d, gap=aisle)
                for p in placed
            )
            if not collision:
                return (x, y)
            y += grid_step
        x += grid_step
    return None


# ── 배치 알고리즘 ────────────────────────────────────────
def _pack_orders(
    orders: list[Order],
    zone: FactoryZone,
    specs: dict[str, EquipmentSpec],
    scenario_name: str,
    allow_rotate: bool = True,
) -> LayoutScenario:
    """주어진 순서로 설비를 Zone에 배치"""
    scenario = LayoutScenario(name=scenario_name, zone_id=zone.zone_id, zone=zone)
    aisle = zone.aisle_width_m

    for order in orders:
        spec = specs.get(order.eq_code)
        if spec:
            w, d = spec.width_m * spec.area_factor ** 0.5, spec.depth_m * spec.area_factor ** 0.5
        else:
            # spec 없으면 면적 기준으로 정방형 추정
            side = order.area_sqm ** 0.5
            w, d = side, side

        pos = _find_position(zone, w, d, scenario.placed, aisle)

        # 회전 시도
        if pos is None and allow_rotate:
            pos = _find_position(zone, d, w, scenario.placed, aisle)
            if pos:
                w, d = d, w
                rotated = True
            else:
                rotated = False
        else:
            rotated = False

        if pos:
            scenario.placed.append(PlacedEquipment(
                order=order, spec=spec,
                x=pos[0], y=pos[1], w=w, d=d,
                rotated=rotated,
            ))
        else:
            scenario.unplaced.append(order)

    return scenario


# ── 시나리오 생성 ─────────────────────────────────────────
def generate_scenarios(
    zone: FactoryZone,
    orders: list[Order],
    specs: dict[str, EquipmentSpec],
) -> list[LayoutScenario]:
    """
    3가지 시나리오를 생성합니다:
    1. 표준 (제작 시작일 순)
    2. 우선순위 순 (High > Medium > Low, 면적 큰 것 우선)
    3. 면적 내림차순 (큰 설비 먼저 배치 - 공간 효율 최대화)
    """
    priority_map = {"High": 0, "Medium": 1, "Low": 2}

    sorted_by_date  = sorted(orders, key=lambda o: o.mfg_start)
    sorted_by_prio  = sorted(orders, key=lambda o: (priority_map.get(o.priority, 9), -o.area_sqm))
    sorted_by_area  = sorted(orders, key=lambda o: -o.area_sqm)

    scenarios = [
        _pack_orders(sorted_by_date,  zone, specs, "시나리오A: 납기일 순"),
        _pack_orders(sorted_by_prio,  zone, specs, "시나리오B: 우선순위 순"),
        _pack_orders(sorted_by_area,  zone, specs, "시나리오C: 대형 설비 우선"),
    ]
    return scenarios


def pick_best(scenarios: list[LayoutScenario]) -> LayoutScenario:
    """점수가 가장 낮은(최적) 시나리오 반환"""
    return min(scenarios, key=lambda s: s.score)


def compare_scenarios(scenarios: list[LayoutScenario]) -> None:
    """시나리오 비교 결과를 콘솔 출력"""
    best = pick_best(scenarios)
    print("\n" + "="*65)
    print("  멀티 시나리오 비교")
    print("="*65)
    print(f"{'시나리오':<28} {'배치':>4} {'미배치':>4} {'가동률':>7} {'점수':>7} {'추천'}")
    print("-"*65)
    for s in scenarios:
        mark = " ★ 최적" if s.name == best.name else ""
        print(
            f"{s.name:<28} {len(s.placed):>4} {len(s.unplaced):>4} "
            f"{s.utilization*100:>6.1f}% {s.score:>7.1f}{mark}"
        )
    print("="*65)
    print(f"\n[추천] {best.name}")
    print(f"  배치 설비: {len(best.placed)}대 | 미배치: {len(best.unplaced)}대 | "
          f"가동률: {best.utilization*100:.1f}%")
    if best.unplaced:
        print(f"  미배치 설비: {', '.join(o.project_id for o in best.unplaced)}")
