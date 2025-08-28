import streamlit as st

def render():
    st.title("🛠 구축 매뉴얼")

    manual_sections = {
        "0. 프로젝트 목적": """
        - 정책·사회적 맥락: 세계와 한국의 탄소중립 진행 상황을 숫자와 추세로 확인 → “지금 속도로 목표 도달 가능한가?”에 대한 객관적 답변 제공
        - 데이터 기반 의사결정: 국가·부문별 배출 변화를 비교 → 효과가 큰 감축 지점 도출
        - 엔드투엔드 인프라 역량 검증: 데이터 적재 → DB → 분석 → 시각화 → CI/CD → 모니터링까지 직접 구축
        - 재현성과 신뢰성: Kaggle 데이터셋을 버전 고정·스키마 표준화하여 적재, ETL 로그·메트릭 관리
        - 현실적 활용: 목표 대비 격차, 부문별 기여도, 글로벌 점유율/누적 배출 → 정책·투자 판단 보조
        - 개인적 목표(Infra Engineer 포트폴리오): Kubernetes 운영, PVC, 시크릿·보안, 관측성, 롤링 배포 등 실무형 인프라 기술 증명
        """,

        "1. 시스템 아키텍처": """
        - VM Oracle Linux 8.9
        - Bridged Network 192.168.4.0/24 + NAT
        - Kubernetes Cluster (1 Master + 3 Worker)
          * Worker1: Frontend
          * Worker2: Backend
          * Worker3: Monitoring
        - 외부 연동: GitHub → GHCR → GitHub Actions → Kubernetes 배포
        - 모니터링: Prometheus + Grafana
        - DB 서버: PostgreSQL (192.168.4.105)
        """,

        "2. 요구사항": """
        - OS: Oracle Linux 8.9
        - Memory: 최소 4GB (Master/Worker 각 VM)
        - 네트워크: 192.168.4.101 ~ 192.168.4.105 (브릿지 + NAT)
        """,

        "3. 사전 준비": """
        - VM 서버 환경: Vagrant + Oracle Linux 8.9
        - 방화벽 포트 오픈 목록
          * 22 (SSH), 80/443 (HTTP/HTTPS), 5432 (PostgreSQL)
          * 6443 (K8s API Server), 2379–2380 (etcd), 10250 (Kubelet)
          * 10257, 10259 (Controller/Scheduler)
          * 30000–32767 (NodePort)
          * 9090 (Prometheus), 8501 (Streamlit Frontend)
        - 필수 설치 도구
          * Git, Docker & Containerd
          * kubectl, kubeadm, kubelet
          * Helm
          * PostgreSQL Client (psql)
        """,

        "4. 데이터베이스 설정 (PostgreSQL)": """
        - PostgreSQL 선택 이유: 안정성, 오픈소스, 시계열 데이터 적합성
        - 사용자: app
        - 데이터베이스: appdb
        - conf 수정
          * postgresql.conf → listen_addresses = '*'
          * pg_hba.conf → host all all 192.168.4.0/24 md5
        - 접속 테스트
          psql -h 192.168.4.105 -U app -d appdb
        """,

        "5. 애플리케이션 환경 (Streamlit)": """
        - .env 구성
          DB_HOST=192.168.4.105
          DB_PORT=5432
          DB_NAME=appdb
          DB_USER=app
          DB_PASSWORD=apppw
          CSV_TABLE=data
          FRONTEND_PORT=8501
        - requirements.txt
          streamlit, pandas, sqlalchemy, psycopg[binary], python-dotenv
        """,

        "6. 컨테이너화 (Docker)": """
        - Dockerfile 작성
        ```dockerfile
        FROM python:3.11-slim
        WORKDIR /app
        COPY requirements.txt .
        RUN pip install -r requirements.txt
        COPY . .
        CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
        ```
        - GHCR 푸시
          docker build -t ghcr.io/<user>/carbon-frontend:main .
          docker push ghcr.io/<user>/carbon-frontend:main
        """,

        "7. 쿠버네티스 배포": """
        - Deployment
          * replicas=1
          * image=ghcr.io/<user>/carbon-frontend:main
          * envFrom: ConfigMap, Secret
        - Service (NodePort)
        ```yaml
        apiVersion: v1
        kind: Service
        metadata:
          name: carbon-frontend
          namespace: data
        spec:
          type: NodePort
          selector:
            app: carbon-frontend
          ports:
            - port: 8501
              targetPort: 8501
              nodePort: 32001
        ```
        - ConfigMap: DB 설정 등 일반 환경변수
        - Secret: DB 비밀번호 등 민감 정보
        - PVC: **NFS 기반 스토리지** 사용 (Prometheus, Grafana, Loki 데이터 보존)
        """,

        "8. CI/CD 파이프라인": """
        - GitHub Actions 워크플로우
        - 코드 푸시 → 자동 빌드 → GHCR Push → K8s 배포
        - 롤링 업데이트 방식으로 중단 없는 배포
        """,

        "9. 모니터링 & 로깅": """
        - Prometheus / Grafana 설치
        - 대시보드 확인
        - Alert 설정 (선택적)
        """,

        "10. 문제 해결 (Troubleshooting)": """
        - Vagrant Calico: kubeadm join 시 CIDR 감지 문제 → 감지기 설정 필요
        - Pod CrashLoopBackOff
          * 원인: 잘못된 이미지, env 설정 오류, PVC 바인딩 실패
          * 해결: kubectl describe/logs 확인 후 수정
        - 이미지 Pull 실패
          * 원인: imagePullSecret 미설정, GHCR 인증 실패
          * 해결: kubectl create secret docker-registry 로 GHCR secret 등록
        - DB 연결 오류
          * 원인: 방화벽 미개방, pg_hba.conf 미설정, 잘못된 비밀번호
          * 해결: 5432 포트 확인, conf 수정 후 PostgreSQL 재시작
        """
    }

    section = st.sidebar.radio("📚 매뉴얼 목차", list(manual_sections.keys()))
    st.markdown(manual_sections[section])
