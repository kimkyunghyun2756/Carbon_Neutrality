#!/bin/bash
set -e

# ====== 필수 패키지 설치 ======
echo "필수 패키지 확인 중..."
if ! command -v curl &> /dev/null || ! command -v wget &> /dev/null; then
  echo "curl, wget 설치 중..."
  sudo yum install -y curl wget
  echo "curl, wget 설치 완료"
else
  echo "curl, wget 이미 설치됨"
fi

# ====== kubectl-neat 설치 확인 및 설치 ======
if ! command -v kubectl-neat &> /dev/null; then
  echo " kubectl-neat 설치 중..."

  # GitHub API에서 최신 릴리스 버전 가져오기
  LATEST_VERSION=$(curl -s https://api.github.com/repos/itaysk/kubectl-neat/releases/latest \
    | grep "tag_name" \
    | cut -d '"' -f 4)

  echo "➡️ 최신 버전: $LATEST_VERSION"

  # 최신 버전 바이너리 다운로드 (Linux amd64 기준)
  wget -q "https://github.com/itaysk/kubectl-neat/releases/download/${LATEST_VERSION}/kubectl-neat_linux_amd64" -O /tmp/kubectl-neat
  sudo mv /tmp/kubectl-neat /usr/local/bin/
  sudo chmod +x /usr/local/bin/kubectl-neat

  echo "kubectl-neat ${LATEST_VERSION} 설치 완료"
else
  echo "kubectl-neat 이미 설치됨"
fi

# ====== 백업 디렉토리 ======
BACKUP_DIR="k8s-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p $BACKUP_DIR

echo "쿠버네티스 리소스 백업 시작..."
echo "저장 위치: $BACKUP_DIR"

# ====== 네임스페이스 단위 리소스 백업 ======
for ns in $(kubectl get ns --no-headers -o custom-columns=":metadata.name"); do
  echo "➡️ Namespace: $ns"
  mkdir -p $BACKUP_DIR/$ns

  for res in $(kubectl api-resources --verbs=list --namespaced -o name); do
    kubectl get $res -n $ns -o yaml 2>/dev/null > $BACKUP_DIR/$ns/$res.yaml || true
  done
done

# ====== 클러스터 범위 리소스 백업 ======
echo "Cluster-wide 리소스"
mkdir -p $BACKUP_DIR/cluster-resources
for res in $(kubectl api-resources --verbs=list --namespaced=false -o name); do
  kubectl get $res -o yaml 2>/dev/null $BACKUP_DIR/cluster-resources/$res.yaml || true
done

echo "백업 완료: $BACKUP_DIR"
echo "chmod +x backup.sh 명령어를 실행하여 권한을 변경해주세요"
echo "./backup.sh 명령어로 스크립트를 실행 할 수 있습니다"
