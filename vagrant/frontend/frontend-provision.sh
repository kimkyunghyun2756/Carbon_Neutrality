#!/usr/bin/env bash
# frontend-provision.sh
# - Vagrantfile의 env: 해시로 전달된 값을 받아 워커(백엔드) 노드 조인
# - 값들을 /etc/cluster/env 로 영구 저장하여 이후에도 재사용

exec > >(tee -a /var/log/provision-frontend.log) 2>&1
set -euo pipefail

##### 0) Vagrant env에서 내려온 값들(없으면 기본값) #####
NODE_IP="${NODE_IP:-192.168.4.102}"       # 이 노드 IP (kubelet --node-ip)
MASTER_IP="${MASTER_IP:-192.168.4.101}"   # master-provision이 :8000으로 join.sh/config 서빙
JOIN_PORT="${JOIN_PORT:-8000}"
K8S_TRACK="${K8S_TRACK:-v1.30}"           # pkgs.k8s.io 트랙
USE_DOCKER="${USE_DOCKER:-false}"         # containerd만 쓰면 false

# 라벨/테인트(선택)
NODE_LABELS="${NODE_LABELS:-role=frontend,tier=app}"
NODE_TAINTS="${NODE_TAINTS:-}"            # 예: "dedicated=frontend:NoSchedule"

##### 1) 값 영구 저장 (systemd 등에서 재사용) #####
install -d /etc/cluster
cat >/etc/cluster/env <<EOF
NODE_IP=${NODE_IP}
MASTER_IP=${MASTER_IP}
JOIN_PORT=${JOIN_PORT}
K8S_TRACK=${K8S_TRACK}
USE_DOCKER=${USE_DOCKER}
NODE_LABELS=${NODE_LABELS}
NODE_TAINTS=${NODE_TAINTS}
EOF

# 보조 함수: master의 admin.conf 내려받아 kubectl에 사용
fetch_admin_kubeconfig() {
  mkdir -p /root/.kube
  curl -fsSL "http://${MASTER_IP}:${JOIN_PORT}/config" -o /root/.kube/config
  chmod 600 /root/.kube/config || true
}
kubectl_m() { KUBECONFIG=/root/.kube/config kubectl "$@"; }

echo "[0] 필수 패키지"
dnf -y install dnf-plugins-core curl ca-certificates tar jq \
              iproute iptables ebtables ethtool ipvsadm conntrack firewalld python3 || true
systemctl enable --now firewalld || true

echo "[1] containerd 설치 및 SystemdCgroup=true"
dnf config-manager --add-repo=https://download.docker.com/linux/centos/docker-ce.repo -y || true
dnf -y install containerd.io || true
mkdir -p /etc/containerd
containerd config default | tee /etc/containerd/config.toml >/dev/null
sed -i '/\[plugins."io.containerd.grpc.v1.cri".containerd.runtimes.runc.options\]/,/\[.*\]/ s/SystemdCgroup = false/SystemdCgroup = true/' /etc/containerd/config.toml
systemctl enable --now containerd

if [ "${USE_DOCKER}" = "true" ]; then
  echo "[1-1] (옵션) Docker도 설치/기동"
  dnf -y install docker-ce docker-ce-cli || true
  systemctl enable --now docker || true
fi

echo "[2] kubeadm/kubelet/kubectl 설치 (${K8S_TRACK})"
cat >/etc/yum.repos.d/kubernetes.repo <<EOF
[kubernetes]
name=Kubernetes
baseurl=https://pkgs.k8s.io/core:/stable:/${K8S_TRACK}/rpm/
enabled=1
gpgcheck=1
gpgkey=https://pkgs.k8s.io/core:/stable:/${K8S_TRACK}/rpm/repodata/repomd.xml.key
exclude=kubelet kubeadm kubectl cri-tools kubernetes-cni
EOF
dnf clean all || true; rm -rf /var/cache/dnf || true; dnf makecache || true
dnf install -y kubelet kubeadm kubectl --disableexcludes=kubernetes
systemctl enable --now kubelet

echo "[3] kubelet --node-ip=${NODE_IP}"
KUBELET_CONFIG="/etc/sysconfig/kubelet"
NODE_IP_ARG="--node-ip=${NODE_IP}"
if [ ! -f "$KUBELET_CONFIG" ]; then
  echo "KUBELET_EXTRA_ARGS=${NODE_IP_ARG}" > "$KUBELET_CONFIG"
else
  if grep -q "^KUBELET_EXTRA_ARGS=" "$KUBELET_CONFIG"; then
    sed -i "s|^KUBELET_EXTRA_ARGS=.*|KUBELET_EXTRA_ARGS=${NODE_IP_ARG}|" "$KUBELET_CONFIG"
  else
    echo "KUBELET_EXTRA_ARGS=${NODE_IP_ARG}" >> "$KUBELET_CONFIG"
  fi
fi
systemctl restart kubelet || true

echo "[4] Swap off & 커널 파라미터"
swapoff -a || true
sed -ri '/\s+swap\s+/d' /etc/fstab || true
modprobe br_netfilter || true
cat >/etc/sysctl.d/k8s.conf <<'EOF'
net.bridge.bridge-nf-call-ip6tables = 1
net.bridge.bridge-nf-call-iptables  = 1
net.ipv4.ip_forward                 = 1
EOF
sysctl --system

echo "[5] 방화벽(필수 포트) 반영"
# kubelet
firewall-cmd --add-port=10250/tcp --permanent || true
# NodePort (앱 노출 시)
firewall-cmd --add-port=30000-32767/tcp --permanent || true
# Calico VXLAN (워커에서도 필요)
firewall-cmd --add-port=4789/udp --permanent || true
firewall-cmd --reload || true

echo "[6] 이미 조인되어 있는지 확인"
if [ -f /etc/kubernetes/kubelet.conf ]; then
  echo " - kubelet.conf 존재: 이미 조인됨으로 간주 → 조인 스킵"
  ALREADY_JOINED=1
else
  ALREADY_JOINED=0
fi

if [ "$ALREADY_JOINED" -eq 0 ]; then
  echo "[7] master에서 join.sh 내려받아 실행 (http://${MASTER_IP}:${JOIN_PORT}/join.sh)"
  install -d /opt/join

  tries=30; delay=5; i=1
  while [ $i -le $tries ]; do
    if curl -fsSL "http://${MASTER_IP}:${JOIN_PORT}/join.sh" -o /opt/join/join.sh; then
      break
    fi
    echo "  join.sh 아직 준비 안 됨 (try $i/$tries). ${delay}s 대기 후 재시도..."
    i=$((i+1)); sleep $delay
  done

  chmod +x /opt/join/join.sh
  if ! /opt/join/join.sh; then
    echo "[ERROR] kubeadm join 실패(토큰 만료 가능). 마스터에서 새 토큰으로 join.sh 갱신하세요:"
    echo "        kubeadm token create --ttl 0 --print-join-command > /home/vagrant/project/join.sh"
    exit 1
  fi
fi

echo "[8] (옵션) 라벨/테인트 적용"
if [ -n "${NODE_LABELS}" ] || [ -n "${NODE_TAINTS}" ]; then
  fetch_admin_kubeconfig || true
  NODENAME="$(hostname -s)"
  if [ -n "${NODE_LABELS}" ]; then
    IFS=',' read -ra KV <<< "${NODE_LABELS}"
    for kv in "${KV[@]}"; do
      kubectl_m label node "${NODENAME}" "${kv}" --overwrite || true
    done
  fi
  if [ -n "${NODE_TAINTS}" ]; then
    IFS=',' read -ra T <<< "${NODE_TAINTS}"
    for t in "${T[@]}"; do
      kubectl_m taint node "${NODENAME}" "${t}" --overwrite || true
    done
  fi
fi

echo "[완료] 프론트엔드 노드 준비 완료. node-ip=${NODE_IP}, master=${MASTER_IP}:${JOIN_PORT}"
