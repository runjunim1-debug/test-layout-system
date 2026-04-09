# 설비 Layout 배치 시스템 — 파일럿 기술 문서

PVD 설비 제작 공장의 수주 Forecast 기반 레이아웃 배치 자동화 파일럿  

---

## 1. 기술 스택

| 항목 | 내용 |
|---|---|
| 언어 | Python 3.10+ |
| 웹 프레임워크 | Streamlit 1.35+ |
| 차트 라이브러리 | Plotly 5.20+ (인터랙티브 웹 차트) |
| 데이터 처리 | pandas 2.0+ |
| 수치 계산 | numpy 1.24+ |
| 정적 차트 | matplotlib 3.7+ (outputs/ 이미지 저장용) |

---

## 2. 프로젝트 구조

```
test-layout-system/
│
├── app.py                    # Streamlit 웹앱 진입점
├── main.py                   # CLI 실행 진입점 (이미지 파일 출력)
├── requirements.txt
│
├── data/
│   ├── factory_zones.json        # 공장 Zone 정의 (F1-A, F1-B, F2, OUTSOURCE)
│   ├── equipment_specs.json      # 설비 12종 스펙 (타입×세대×구성)
│   ├── orders_forecast.csv       # 생성된 수주 샘플 데이터 35건
│   └── generate_sample_orders.py # 샘플 데이터 생성 스크립트
│
├── src/
│   ├── data_loader.py        # 데이터 로딩 & 데이터클래스 정의
│   ├── space_calculator.py   # 월별 면적 가동률 계산 엔진
│   ├── layout_engine.py      # 2D 배치 알고리즘 & 시나리오 생성
│   ├── charts.py             # Plotly 기반 인터랙티브 차트 (웹앱용)
│   └── visualizer.py         # matplotlib 기반 정적 차트 (파일 저장용)
│
└── outputs/                  # main.py 실행 시 생성되는 이미지 파일
```

---

## 3. 실행 흐름

### 3-1. 웹앱 실행 흐름 (`app.py`)

```
[브라우저 접속]
       │
       ▼
[Streamlit 서버 시작]
  python -m streamlit run app.py
       │
       ▼
[데이터 로드 - 캐싱]  ← @st.cache_data (재실행 시 재로드 생략)
  data_loader.load_all()
  ├── factory_zones.json   → dict[zone_id, FactoryZone]
  ├── equipment_specs.json → dict[code, EquipmentSpec]
  └── orders_forecast.csv  → list[Order]
       │
       ▼
[사이드바 필터 적용]
  Zone / 설비 타입 / 납기 구분 선택
       │
       ▼
[월별 가동률 계산]
  space_calculator.calculate_monthly_usage()
       │
  ┌────┴─────────────────────────────────────┐
  ▼                                          ▼
[탭 1: 대시보드]                      [탭 2: 레이아웃 배치]
  KPI 카드                              배치 시나리오 3종 생성
  월별 가동률 차트                       layout_engine.generate_scenarios()
  공간 초과 경고/추천                    선택 시나리오 2D 평면도
  Zone 면적 파이차트                     시나리오 비교 레이더 차트

  ▼                                          ▼
[탭 3: Gantt 타임라인]               [탭 4: 수주 현황]
  전체/Zone별 제작 일정                  검색 + 필터링
  단납기/FOB지연 아이콘                  CSV 다운로드
```

### 3-2. CLI 실행 흐름 (`main.py`)

```
python main.py
  │
  ├── STEP 1: 데이터 로드
  ├── STEP 2: 월별 가동률 계산 + 콘솔 출력
  ├── STEP 3: 시나리오 생성 + 비교 출력
  └── STEP 4: 차트 이미지 → outputs/ 저장
              monthly_utilization.png
              gantt_ALL.png / gantt_F1-A.png
              layout_2d_F1-A_시나리오A/B/C.png
              scenario_comparison_radar.png
```

---

## 5. 실행 방법

### 웹앱 실행
```bash
# 패키지 설치 (최초 1회)
pip install -r requirements.txt

# 웹앱 실행
python -m streamlit run app.py
# → 브라우저에서 http://localhost:8501 접속
```

### 샘플 데이터 재생성
```bash
python data/generate_sample_orders.py
```

### CLI 이미지 출력
```bash
python main.py
# → outputs/ 폴더에 PNG 파일 저장
```