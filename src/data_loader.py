"""
데이터 로딩 모듈
- 공장 Zone 정보, 설비 스펙, 수주 Forecast 데이터를 로드하고 전처리
"""
import json
import csv
from datetime import date, datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


# ── 경로 설정 ────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR     = PROJECT_ROOT / "data"


# ── 데이터 클래스 ─────────────────────────────────────────
@dataclass
class FactoryZone:
    zone_id:        str
    factory:        str
    name:           str
    width_m:        float
    depth_m:        float
    total_area:     float
    unusable_area:  float
    usable_area:    float
    aisle_width_m:  float
    max_height_m:   float
    notes:          str = ""

    @property
    def efficiency_ratio(self) -> float:
        """실사용 가능 면적 비율"""
        return self.usable_area / self.total_area if self.total_area > 0 else 0


@dataclass
class EquipmentSpec:
    code:           str
    eq_type:        str       # 저온/고온/RC
    generation:     str       # 대형/중소형
    config:         str       # 1SYS/PRM_Ch
    width_m:        float
    depth_m:        float
    height_m:       float
    area_sqm:       float
    weight_ton:     float
    manpower:       int
    lead_days:      int
    area_factor:    float     # 조립 작업 여유 공간 계수
    notes:          str = ""

    @property
    def working_area_sqm(self) -> float:
        """실제 필요 작업 면적 (설비 면적 × 여유 계수)"""
        return self.area_sqm * self.area_factor


@dataclass
class Order:
    project_id:     str
    customer:       str
    region:         str
    eq_type:        str
    generation:     str
    config:         str
    eq_code:        str
    area_sqm:       float
    delivery_type:  str       # 표준납기/단납기/FOB지연
    lead_days:      int
    mfg_start:      date
    fob_date:       date
    assigned_zone:  str
    status:         str       # 확정/예정
    priority:       str       # High/Medium/Low

    @property
    def is_abnormal(self) -> bool:
        return self.delivery_type != "표준납기"

    @property
    def duration_days(self) -> int:
        return (self.fob_date - self.mfg_start).days

    def active_on(self, check_date: date) -> bool:
        """해당 날짜에 제작 중인지 여부"""
        return self.mfg_start <= check_date <= self.fob_date


# ── 로더 함수 ─────────────────────────────────────────────
def load_factory_zones() -> dict[str, FactoryZone]:
    path = DATA_DIR / "factory_zones.json"
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    zones = {}
    for z in raw["factory"]["zones"]:
        unusable = sum(a["area_sqm"] for a in z["unusable_areas"])
        usable   = z["total_area_sqm"] - unusable
        zones[z["zone_id"]] = FactoryZone(
            zone_id       = z["zone_id"],
            factory       = z["factory"],
            name          = z["name"],
            width_m       = z["width_m"],
            depth_m       = z["depth_m"],
            total_area    = z["total_area_sqm"],
            unusable_area = unusable,
            usable_area   = usable,
            aisle_width_m = z["aisle_width_m"],
            max_height_m  = z["max_height_m"],
            notes         = z.get("notes", ""),
        )
    return zones


def load_equipment_specs() -> dict[str, EquipmentSpec]:
    path = DATA_DIR / "equipment_specs.json"
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    specs = {}
    for s in raw["equipment_types"]["specs"]:
        specs[s["code"]] = EquipmentSpec(
            code        = s["code"],
            eq_type     = s["type"],
            generation  = s["generation"],
            config      = s["config"],
            width_m     = s["width_m"],
            depth_m     = s["depth_m"],
            height_m    = s["height_m"],
            area_sqm    = s["area_sqm"],
            weight_ton  = s["weight_ton"],
            manpower    = s["manpower_required"],
            lead_days   = s["typical_lead_days"],
            area_factor = s["assembly_area_factor"],
            notes       = s.get("notes", ""),
        )
    return specs


def load_orders(specs: Optional[dict[str, EquipmentSpec]] = None) -> list[Order]:
    path = DATA_DIR / "orders_forecast.csv"
    orders = []
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            # 면적: spec에서 working_area 사용 가능 시 반영
            area = float(row["area_sqm"])
            if specs and row["eq_code"] in specs:
                area = specs[row["eq_code"]].working_area_sqm

            orders.append(Order(
                project_id    = row["project_id"],
                customer      = row["customer"],
                region        = row["region"],
                eq_type       = row["eq_type"],
                generation    = row["eq_generation"],
                config        = row["eq_config"],
                eq_code       = row["eq_code"],
                area_sqm      = area,
                delivery_type = row["delivery_type"],
                lead_days     = int(row["lead_days"]),
                mfg_start     = datetime.strptime(row["mfg_start"], "%Y-%m-%d").date(),
                fob_date      = datetime.strptime(row["fob_date"],   "%Y-%m-%d").date(),
                assigned_zone = row["assigned_zone"],
                status        = row["status"],
                priority      = row["priority"],
            ))
    return sorted(orders, key=lambda o: o.mfg_start)


def load_all():
    """편의 함수: 세 가지 데이터를 한 번에 로드"""
    zones = load_factory_zones()
    specs = load_equipment_specs()
    orders = load_orders(specs)
    return zones, specs, orders
