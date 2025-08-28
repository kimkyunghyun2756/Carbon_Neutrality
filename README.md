# 이 프로젝트의 목적

- **정책·사회적 맥락**: 세계와 한국의 탄소중립 진행 상황을 **숫자와 추세**로 객관적으로 확인합니다. “지금 속도로 가면 목표에 도달하는가?”를 데이터로 답합니다.
- **데이터 기반 의사결정**: 국가·부문(전력, 산업, 수송 등)별 배출 변화를 한 화면에서 비교해 **효과가 큰 감축 지점**을 찾습니다.
- **엔드투엔드 인프라 역량 검증**: 데이터 적재 → 저장(DB) → 분석 → 시각화 → **CI/CD** → **모니터링**까지 전 과정을 직접 설계·운영합니다.
- **재현성과 신뢰성**: Kaggle에서 제공하는 공개 데이터셋을 **버전 고정·스키마 표준화**로 적재하고, ETL 로그·메트릭으로 갱신 이력을 관리합니다.
- **현실적 활용**: 목표 대비 격차(Gap), 부문 기여도, 글로벌 점유율/누적 배출을 한눈에 보여 **정책·투자 판단 보조**에 기여합니다.
- **개인적 목표(Infra Engineer 포트폴리오)**: Kubernetes 운영, 스토리지/PVC, 시크릿/보안, 관측성(로그·메트릭·알림), 롤링 배포 등 **실무형 인프라 스킬**을 증명합니다.

---

## 구현 로드맵 (Implementation Roadmap)

- **데이터**: Kaggle Dataset 기반 수집 및 전처리  
- **저장(DB)**: PostgreSQL (정규화 테이블 + 뷰)  
- **분석/지표**: 추세선, 증감률, 목표 대비 격차, 글로벌 점유율  
- **시각화**: Streamlit 대시보드(국가/부문/기간 필터)  
- **쿠버네티스(Kubernetes)**:  
  - **CRI(Container Runtime Interface)**: containerd  
  - **CNI(Container Network Interface)**: Calico (Pod 네트워킹)  
  - **CSI(Container Storage Interface)**: NFS 기반 PVC (Persistent Volume)  
  - **Ingress Controller**: NodePort 
  - **Helm**: 패키지 관리 및 배포 자동화  
  - **Secret/ConfigMap**: DB 접속정보 및 환경변수 관리  
  - **Observability**: Prometheus + Grafana (메트릭/알림), Loki (로그)  
- **CI/CD**: GitHub Actions + GHCR (이미지 빌드/배포)  

---

## 한계와 주의사항

- **지표 해석 차이**: CO₂(연료연소·시멘트) vs. GHG(CO₂e), 영토기반 vs. 소비기반, LULUCF 포함 여부에 따라 값이 달라질 수 있습니다.
- **데이터 갱신 주기**: Kaggle 소스 갱신 시점이 불규칙할 수 있으며 최근 연도 값은 **잠정치**일 수 있습니다.
- **모델링 범위**: 초기 단계에서는 예측/시나리오보다 **관측 데이터 분석**에 집중합니다.

---

## 기대효과 (Outcomes)

- 목표 달성 가능성에 대한 **정량적 근거** 제공
- 부문별 감축 우선순위에 대한 **실용적 인사이트** 제공
- 전 과정 자동화·관측으로 **운영 안정성**과 **학습 가치** 확보

---

## 기술 스택 (요약)

- **Kubernetes**: CRI(containerd), CNI(Calico), CSI(NFS PVC), NodePort, Helm, Secret/ConfigMap  
- **DB**: PostgreSQL  
- **App**: Streamlit  
- **CI/CD**: GitHub Actions + GHCR  
- **Observability**: Prometheus + Grafana

## 리포지토리/모듈 구조 

  ```text
  carbon-dashboard/
  ├─ vagrant/
  │  ├─ master/        # Vagrantfile, provision.sh
  │  ├─ backend/
  │  ├─ frontend/
  │  ├─ monitoring/
  │  └─ db/
  ├─ apps/
  │  ├─ backend/       # FastAPI (Dockerfile 포함)
  │  ├─ frontend/      # Streamlit (Dockerfile 포함)
  │  └─ etl/           # 파이썬 ETL, 유틸
  ├─ .github/
  │  └─ workflow/      # 깃허브 액션 yml
  ├─ k8s/              # 네임스페이스/오버레이/매니페스트
  │  ├─ grafana/       
  │  │  └─ dashboard/  # dashboard config
  │  ├─ frontend/      
  │  └─ etl/           
  ├─ docks/           
  │  └─ img            # 시스템 아키텍쳐 이미지
  └─ data/             # ingress/registry/storage 등 애드온
     ├─ raw            # 원본 데이터 파일
     └─ refined/       # 정제한 데이터 파일
```

## 시스템 아키텍쳐

![Architecture overview](docs/img/System_Architecture_2.png)

# Carbon Dashboard Dataset

이 데이터셋은 국가별 이산화탄소(CO₂) 및 온실가스 배출, 에너지 사용, 인구 및 경제 지표 등을 포함하고 있습니다.  
이재명 정부의 **탄소중립 정책 수립 및 성과 평가**에 필요한 다양한 정보를 담고 있으며,  
부문별 감축 정책, 흡수원 정책, 효율성 정책을 검토하는 데 활용될 수 있습니다.

---

## 컬럼별 정책 목적 정리

| 카테고리 | 주요 컬럼 | 정책 활용 목적 |
|----------|-----------|----------------|
| **인구·경제** | `population`, `gdp`, `energy_per_gdp`, `co2_per_gdp` | 1인당 배출량, 경제성장 대비 탄소 효율, 저탄소 성장 정책 평가 |
| **총 배출 추세** | `co2`, `co2_growth_abs`, `co2_growth_prct`, `co2_including_luc`, `cumulative_co2`, `total_ghg_100y` | 국가 온실가스 총량 및 증가율 모니터링, 감축로드맵 달성 여부 확인 |
| **에너지원별 배출** | `coal_co2`, `oil_co2`, `gas_co2`, `cement_co2`, `flaring_co2` | 탈석탄 정책, 수송부문 전환(석유), 가스 전환, 산업부문 감축 |
| **온실가스 종류별** | `methane`, `nitrous_oxide`, `ghg_per_capita` | 농업·폐기물 부문 정책(메탄, N₂O), 국제 비교(1인당 GHG) |
| **토지·흡수원** | `land_use_change_co2`, `cumulative_luc_co2` | 산림·토지 정책, 흡수원 확보 정책 성과 |
| **효율/국민 체감 지표** | `co2_per_capita`, `*_per_capita` 계열, `co2_per_unit_energy` | 국민 체감도, 국제 비교, 에너지 믹스 탈탄소화 평가 |

---

## 활용
- **대시보드 시각화**: Streamlit 기반 Carbon Dashboard에서 국가별/연도별 배출 추세 시각화  
- **정책 평가**: 탈석탄, 전기차 보급, 산림 복원 등 개별 정책 성과 평가  
- **국제 비교**: 1인당 배출량, GDP 대비 배출량 등을 활용한 국가 간 비교  
- **시뮬레이션**: 감축 시나리오별 탄소중립 로드맵 검증