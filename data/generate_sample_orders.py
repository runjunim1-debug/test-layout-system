"""
수주 Forecast 예시 데이터 생성 스크립트
실행: python data/generate_sample_orders.py
"""
import csv
import random
from datetime import date, timedelta
import os

random.seed(42)

EQUIPMENT_CODES = [
    ("저온", "대형",  "1SYS",   "LT-L-1S", 12.6, 80),
    ("저온", "대형",  "PRM_Ch", "LT-L-PC", 19.25, 80),
    ("저온", "중소형","1SYS",   "LT-M-1S",  6.16, 70),
    ("저온", "중소형","PRM_Ch", "LT-M-PC", 10.64, 75),
    ("고온", "대형",  "1SYS",   "HT-L-1S", 16.8,  80),
    ("고온", "대형",  "PRM_Ch", "HT-L-PC", 24.0,  85),
    ("고온", "중소형","1SYS",   "HT-M-1S",  8.0,  72),
    ("고온", "중소형","PRM_Ch", "HT-M-PC", 13.44, 78),
    ("RC",   "대형",  "1SYS",   "RC-L-1S", 22.0,  85),
    ("RC",   "대형",  "PRM_Ch", "RC-L-PC", 31.5,  90),
    ("RC",   "중소형","1SYS",   "RC-M-1S", 11.4,  75),
    ("RC",   "중소형","PRM_Ch", "RC-M-PC", 17.5,  80),
]

ZONES = ["F1-A", "F1-B", "F2", "OUTSOURCE"]
ZONE_WEIGHTS = [0.35, 0.25, 0.30, 0.10]

DELIVERY_TYPES = ["표준납기", "단납기", "FOB지연"]
DELIVERY_WEIGHTS = [0.70, 0.20, 0.10]

CUSTOMERS = [
    "삼성전자", "SK하이닉스", "LG디스플레이",
    "마이크론", "TSMC", "인텔", "키옥시아"
]

REGIONS = ["국내", "미주", "유럽", "아시아"]
REGION_WEIGHTS = [0.30, 0.25, 0.25, 0.20]


def generate_orders(n=35, start_date=date(2025, 1, 1)):
    orders = []
    for i in range(n):
        eq = random.choices(EQUIPMENT_CODES, weights=[2,1,3,2,2,1,3,2,1,1,2,1])[0]
        eq_type, eq_gen, eq_config, eq_code, area_sqm, std_lead = eq

        delivery_type = random.choices(DELIVERY_TYPES, weights=DELIVERY_WEIGHTS)[0]

        if delivery_type == "표준납기":
            lead_days = std_lead
        elif delivery_type == "단납기":
            lead_days = int(std_lead * random.uniform(0.55, 0.75))
        else:  # FOB지연
            lead_days = int(std_lead * random.uniform(1.10, 1.30))

        # 제작 시작일: 2025-01 ~ 2025-06 분산
        offset_days = random.randint(0, 180)
        mfg_start = start_date + timedelta(days=offset_days)
        fob_date = mfg_start + timedelta(days=lead_days)

        zone = random.choices(ZONES, weights=ZONE_WEIGHTS)[0]
        customer = random.choice(CUSTOMERS)
        region = random.choices(REGIONS, weights=REGION_WEIGHTS)[0]

        project_id = f"PJT-2025-{i+1:03d}"

        orders.append({
            "project_id":    project_id,
            "customer":      customer,
            "region":        region,
            "eq_type":       eq_type,
            "eq_generation": eq_gen,
            "eq_config":     eq_config,
            "eq_code":       eq_code,
            "area_sqm":      area_sqm,
            "delivery_type": delivery_type,
            "lead_days":     lead_days,
            "mfg_start":     mfg_start.strftime("%Y-%m-%d"),
            "fob_date":      fob_date.strftime("%Y-%m-%d"),
            "assigned_zone": zone,
            "status":        random.choice(["확정", "확정", "확정", "예정"]),
            "priority":      random.choice(["High", "High", "Medium", "Medium", "Low"]),
        })

    # 제작 시작일 오름차순 정렬
    orders.sort(key=lambda x: x["mfg_start"])
    return orders


def main():
    orders = generate_orders(n=35)

    out_dir = os.path.dirname(__file__)
    out_path = os.path.join(out_dir, "orders_forecast.csv")

    fieldnames = [
        "project_id", "customer", "region",
        "eq_type", "eq_generation", "eq_config", "eq_code",
        "area_sqm", "delivery_type", "lead_days",
        "mfg_start", "fob_date", "assigned_zone",
        "status", "priority"
    ]

    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(orders)

    print(f"[완료] 수주 데이터 {len(orders)}건 생성 → {out_path}")
    for o in orders[:5]:
        print(f"  {o['project_id']} | {o['eq_code']} | {o['mfg_start']} ~ {o['fob_date']} | {o['assigned_zone']} | {o['delivery_type']}")


if __name__ == "__main__":
    main()
