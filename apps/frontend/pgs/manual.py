import streamlit as st

def render():
    st.title("구축 매뉴얼")

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
        - CPU: Master 최소 2 vCPU, Worker 최소 1~2 vCPU
        - Memory: VM당 최소 4GB
        - Disk: VM당 최소 20GB, NFS 서버 필요
        - 네트워크: 192.168.4.101 ~ 192.168.4.105 (브릿지 + NAT)
        - 기타
          * GitHub 계정 및 GHCR Token
          * Vagrant + VirtualBox
          * DNS 혹은 /etc/hosts 설정
        """,

        "3. 사전 준비": """
        - VM 서버 환경: Vagrant + Oracle Linux 8.9
        - vagrant 파일 작성
        ```vagrantfile
        # -*- mode: ruby -*-
        # vi: set ft=ruby :

        Vagrant.configure("2") do |config|
          # SSH/부팅 안정화 (유효한 키만 사용)
          config.ssh.keep_alive          = true
          config.ssh.connect_retries     = 60     # 총 재시도 횟수
          config.ssh.connect_retry_delay = 5      # 재시도 간격(초)
          config.ssh.connect_timeout     = 30     # 1회 연결 타임아웃(초)
          config.vm.boot_timeout         = 600    # 부팅 대기(초)
          config.vm.box_check_update     = false
          config.vm.define "k8s-master-cp" do |cfg|
            cfg.vm.box = "generic/oracle8"
            cfg.vm.host_name = "k8s-master-cp"

            cfg.vm.network "public_network",
              bridge: "Intel(R) Wi-Fi 6 AX201 160MHz",
              ip: "192.168.4.101",
              use_dhcp_assigned_default_route: false

            cfg.vm.network "forwarded_port", guest: 22, host: 60000, auto_correct: true, id: "ssh"

            cfg.vm.synced_folder ".", "/vagrant", disabled: true

            cfg.vm.provider "virtualbox" do |vb|
              vb.name   = "k8s-master-cp"
              vb.cpus   = 4
              vb.memory = 6144
              vb.customize ["modifyvm", :id, "--rtcuseutc", "on", "--groups", "/k8s-carbon"]
              # 디버깅 필요 시 GUI 켜기:
              # vb.gui = true
            end

            cfg.vm.provision "shell",
              path: "master-provision.sh",
              privileged: true,
              env: {
                "API_IP"         => "192.168.4.101",
                "POD_CIDR"       => "10.244.0.0/16",
                "K8S_TRACK"      => "v1.30",
                "CALICO_VER"     => "v3.30.2",
                "CALICO_MTU"     => "1450",
                "GW_IP"          => "192.168.4.1",
                "SINGLE_NODE"    => "false",
                "NODE_THRESHOLD" => "2",
                "SLEEP_SEC"      => "10"
              }
          end
        end
        ```
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
        - PostgreSQL 선택 이유
          * 오픈소스 RDBMS 중 가장 안정적이며 커뮤니티/생태계가 활발  
          * 시계열·대용량 데이터 처리 적합 (Window Function, CTE 등 분석 쿼리 지원)  
          * JSON/JSONB 컬럼 지원 → 반정형 데이터도 처리 가능  
          * 확장성: TimescaleDB 같은 시계열 확장 모듈과 연동 가능  
          * 성능 최적화 옵션 풍부 (인덱스, 파티셔닝, 병렬 쿼리)  
          * MySQL 대비 강력한 표준 SQL 준수도 및 트랜잭션 안정성  
          * Kubernetes 환경과 잘 맞음 (Helm chart, StatefulSet 배포 용이)  
          * 향후 Data Warehouse, BI 툴과의 연동성 우수 (Metabase, Grafana 등)  
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
          docker build -t ghcr.io/kimkyunghyun2756/carbon-frontend:main .
          docker push ghcr.io/kimkyunghyun2756/carbon-frontend:main
        """,

        "7. 쿠버네티스 설정 (구성 요소 & 선택 이유)": """
        - 네트워크 플러그인: Calico
          * 이유: CNI 중 가장 널리 사용, NetworkPolicy 지원, Vagrant 환경에서 안정적 동작  
          * 대안: Flannel(구현 단순하지만 기능 제한), Cilium(eBPF 기반이지만 학습 곡선 높음)  

        - 로드밸런서: MetalLB
          * 이유: 온프레미스 환경에서는 클라우드 LB가 없음 → L2 모드로 로컬 IP풀 제공  
          * 대안: Ingress-Nginx 단독 사용 가능하나 외부 접근 NodePort 의존 → 불편  

        - 스토리지: NFS Subdir External Provisioner
          * 이유: 단순, 가볍고 Vagrant/VM에서도 활용 가능  
          * 대안: Longhorn(고가용성 제공하지만 디스크 자원 필요), Ceph(운영 복잡도 높음)  

        - 모니터링: Prometheus + Grafana
          * 이유: CNCF 표준, Helm 차트로 설치 용이, Alertmanager 확장 가능  
          * 사이드카: Prometheus-config-reloader  
            → ConfigMap 변경 시 자동 반영 (무중단 설정 업데이트 지원)  

        - CI/CD 연동: GitHub Actions + GHCR
          * 이유: GitHub 기반 워크플로우에 최적화, 인증/배포 Secret 관리 용이  
          * 대안: Jenkins(더 강력하지만 무겁고 유지비용 큼)  

        - 보안/비밀 관리: Kubernetes Secret
          * DB 비밀번호, GHCR 토큰을 Secret으로 관리  
          * 사이드카: 없고, 환경변수/Secret mount 방식 채택  
        """,

        "8. 쿠버네티스 배포": """
        - Deployment
          * replicas=1
          * image=ghcr.io/kimkyunghyun2756/carbon-frontend:main
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

        "9. CI/CD 파이프라인": """
        - GitHub Actions 워크플로우
        - 코드 푸시 → 자동 빌드 → GHCR Push → K8s 배포
        - 롤링 업데이트 방식으로 중단 없는 배포
        """,

        "10. 모니터링 & 로깅": """
        - Prometheus / Grafana 설치
        - 대시보드 확인
        - Alert 설정 (미선택)
        """,

        "11. 문제 해결 (Troubleshooting)": """
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

    section = st.sidebar.radio("매뉴얼 목차", list(manual_sections.keys()))
    st.markdown(manual_sections[section])
    
    if section == "1. 시스템 아키텍처":
        st.image(
            "https://raw.githubusercontent.com/kimkyunghyun2756/Carbon_Neutrality/main/docs/img/System_Architecture_2.png",
            caption="시스템 아키텍처 다이어그램",
            use_column_width=True
        )