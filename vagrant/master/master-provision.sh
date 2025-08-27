#!/bin/bash
exec > >(tee -a /var/log/provision.log) 2>&1
set -euo pipefail

##### 사용자 변수(필요시 Vagrantfile에서 override) #####
API_IP="${API_IP:-192.168.4.101}"         # control-plane 브리지 IP
POD_CIDR="${POD_CIDR:-10.244.0.0/16}"     # kubeadm --pod-network-cidr와 일치
K8S_TRACK="${K8S_TRACK:-v1.30}"           # pkgs.k8s.io 트랙
CALICO_VER="${CALICO_VER:-v3.30.2}"       # Calico 릴리스 태그
CALICO_MTU="${CALICO_MTU:-1450}"          # VXLAN/가상화 환경 권장
GW_IP="${GW_IP:-192.168.4.1}"             # can-reach 대상 게이트웨이
SINGLE_NODE="${SINGLE_NODE:-false}"       # true: 컨트롤플레인 taint 제거
NODE_THRESHOLD="${NODE_THRESHOLD:-2}"     # (마스터+워커) 노드 수가 이 값 이상이면 Calico 설치
SLEEP_SEC="${SLEEP_SEC:-10}"              # watcher 폴링 주기(초)

# 프로비저닝/서비스 공유용 환경파일
install -d /etc/cluster
cat >/etc/cluster/env <<EOF
API_IP=${API_IP}
POD_CIDR=${POD_CIDR}
CALICO_VER=${CALICO_VER}
CALICO_MTU=${CALICO_MTU}
GW_IP=${GW_IP}
SINGLE_NODE=${SINGLE_NODE}
NODE_THRESHOLD=${NODE_THRESHOLD}
SLEEP_SEC=${SLEEP_SEC}
EOF

##### 재시도 래퍼 #####
RETRY_MAX=${RETRY_MAX:-5}
RETRY_DELAY=${RETRY_DELAY:-5}
retry() {
  local n=0
  until "$@"; do
    n=$((n+1))
    [ $n -ge $RETRY_MAX ] && echo "[ERROR] retry exceeded: $*" && return 1
    echo "[retry $n/${RETRY_MAX}] $* ; sleep ${RETRY_DELAY}s"
    sleep "$RETRY_DELAY"
  done
}

echo "[0] 필수 패키지 & firewalld"
retry dnf -y install dnf-plugins-core curl ca-certificates tar jq iproute \
               iptables ebtables ethtool ipvsadm firewalld python3 || true
# systemctl enable --now firewalld || true

echo "[1] Docker & containerd 설치"
dnf config-manager --add-repo=https://download.docker.com/linux/centos/docker-ce.repo -y
dnf -y install docker-ce docker-ce-cli containerd.io || true

echo "[2] containerd 설정(SystemdCgroup)"
mkdir -p /etc/containerd
containerd config default | tee /etc/containerd/config.toml >/dev/null
sed -i '/\[plugins."io.containerd.grpc.v1.cri".containerd.runtimes.runc.options\]/,/\[.*\]/ s/SystemdCgroup = false/SystemdCgroup = true/' /etc/containerd/config.toml
systemctl enable --now containerd
systemctl enable --now docker || true   # 필요 없으면 꺼도 무방

echo "[3] Kubernetes repo & 설치"
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

echo "[3-1] kubelet --node-ip=${API_IP}"
KUBELET_CONFIG="/etc/sysconfig/kubelet"
NODE_IP_ARG="--node-ip=${API_IP}"
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

echo "[5] 방화벽(K8s/API/HTTP/Calico VXLAN)"
retry dnf -y install firewalld
systemctl enable --now firewalld || true
firewall-cmd --add-port=6443/tcp --permanent      || true
firewall-cmd --add-port=2379-2380/tcp --permanent || true
firewall-cmd --add-port=10250/tcp --permanent     || true
firewall-cmd --add-port=10257/tcp --permanent     || true
firewall-cmd --add-port=10259/tcp --permanent     || true
firewall-cmd --add-port=4789/udp --permanent      || true  # Calico VXLAN
firewall-cmd --add-port=8000/tcp --permanent      || true  # join HTTP
firewall-cmd --reload || true

echo "[6] kubeadm init (Pod CIDR=${POD_CIDR})"
if [ ! -f /etc/kubernetes/admin.conf ]; then
  kubeadm init \
    --apiserver-advertise-address="${API_IP}" \
    --pod-network-cidr="${POD_CIDR}" \
    --ignore-preflight-errors=NumCPU
fi

echo "[7] kubeconfig 배포(권한/환경)"
mkdir -p /home/vagrant/.kube
install -m 600 -o vagrant -g vagrant /etc/kubernetes/admin.conf /home/vagrant/.kube/config
export KUBECONFIG=/etc/kubernetes/admin.conf
chmod 644 /etc/kubernetes/admin.conf || true
grep -q 'KUBECONFIG=' /home/vagrant/.bashrc || echo 'export KUBECONFIG=$HOME/.kube/config' >> /home/vagrant/.bashrc

echo "[8] API 준비 대기"
until kubectl get nodes &>/dev/null; do
  echo "  ...waiting kube-apiserver"; sleep 2
done

echo "[9] join.sh + config 생성"
install -d -o vagrant -g vagrant /home/vagrant/project
kubeadm token create --ttl 0 --print-join-command > /home/vagrant/project/join.sh
chmod +x /home/vagrant/project/join.sh
cp -f /etc/kubernetes/admin.conf /home/vagrant/project/config
chown -R vagrant:vagrant /home/vagrant/project

echo "[10] join HTTP systemd 서비스 생성/기동(:8000)"
cat >/etc/systemd/system/join-http.service <<'UNIT'
[Unit]
Description=Serve kubeadm join files on :8000
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=vagrant
WorkingDirectory=/home/vagrant/project
ExecStart=/usr/bin/python3 -m http.server 8000 --bind 0.0.0.0
Restart=on-failure

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now join-http.service

echo "[11] Calico 설치 함수/워커 watcher 배치"
install -d /opt/cluster

# Calico 설치 함수 (나중에 watcher가 호출)
cat >/opt/cluster/provision_functions.sh <<'EOSF'
#!/usr/bin/env bash
set -euo pipefail
# 환경 변수 불러오기
source /etc/cluster/env

install_calico() {
  echo "[Calico] Operator/CR/패치 시작 (CALICO_VER=${CALICO_VER})"

  OP_CRDS_URL="https://raw.githubusercontent.com/projectcalico/calico/${CALICO_VER}/manifests/operator-crds.yaml"
  OP_DEPLOY_URL="https://raw.githubusercontent.com/projectcalico/calico/${CALICO_VER}/manifests/tigera-operator.yaml"
  kubectl apply --server-side -f "${OP_CRDS_URL}"
  kubectl create -f "${OP_DEPLOY_URL}" 2>/dev/null || kubectl apply -f "${OP_DEPLOY_URL}"
  kubectl -n tigera-operator rollout status deploy/tigera-operator --timeout=5m || true

  CR_URL="https://raw.githubusercontent.com/projectcalico/calico/${CALICO_VER}/manifests/custom-resources.yaml"

  # 일시 실패 흡수: create→apply 재시도
  set +e
  tries=6; delay=10; i=1
  while [ $i -le $tries ]; do
    echo "[try $i/${tries}] kubectl create -f custom-resources.yaml"
    kubectl create -f "${CR_URL}"
    rc=$?
    if [ $rc -eq 0 ]; then break; fi
    echo "[warn] create 실패(rc=$rc). apply로 재시도"
    kubectl apply -f "${CR_URL}"
    rc=$?
    [ $rc -eq 0 ] && break
    echo "[warn] apply도 실패(rc=$rc) → ${delay}s 대기"
    i=$((i+1)); sleep $delay
  done
  set -e

  # 환경 patch
  read -r -d '' INSTALL_PATCH <<JSON
{
  "spec": {
    "calicoNetwork": {
      "bgp": "Disabled",
      "mtu": ${CALICO_MTU},
      "ipPools": [
        {
          "cidr": "${POD_CIDR}",
          "encapsulation": "VXLANCrossSubnet",
          "natOutgoing": "Enabled",
          "nodeSelector": "all()"
        }
      ],
      "nodeAddressAutodetectionV4": { "canReach": "${GW_IP}" }
    }
  }
}
JSON
  kubectl patch installation.operator.tigera.io default --type=merge -p "${INSTALL_PATCH}" || true

  echo "[Calico] calico-system 생성 대기"
  ok=0
  for _ in {1..120}; do
    if kubectl get ns calico-system >/dev/null 2>&1; then ok=1; break; fi
    sleep 5
  done

  if [ "$ok" -ne 1 ]; then
    echo "[진단] calico-system 미생성"
    kubectl get installation.operator.tigera.io default -o yaml | sed -n '1,200p' || true
    kubectl -n tigera-operator logs deploy/tigera-operator --tail=300 || true
    kubectl -n tigera-operator get events --sort-by=.lastTimestamp | tail -n 50 || true
    return 0
  fi

  kubectl -n calico-system rollout status ds/calico-node --timeout=10m || true
  kubectl -n calico-system rollout status deploy/calico-kube-controllers --timeout=5m || true

  echo "[Calico] 완료. SINGLE_NODE=${SINGLE_NODE}"
  if [ "${SINGLE_NODE}" = "true" ]; then
    kubectl taint nodes --all node-role.kubernetes.io/control-plane- || true
  fi
}
EOSF
chmod +x /opt/cluster/provision_functions.sh

# 워커 조인 감시기
cat >/usr/local/bin/run-after-first-worker.sh <<'EOW'
#!/usr/bin/env bash
set -euo pipefail
source /etc/cluster/env
source /opt/cluster/provision_functions.sh

LOCK="/var/run/after-first-worker.done"

if [ -f "$LOCK" ]; then
  echo "[watcher] already done"; exit 0
fi

echo "[watcher] waiting until node count >= ${NODE_THRESHOLD}"
while true; do
  COUNT=$(kubectl get nodes --no-headers 2>/dev/null | wc -l | xargs || echo 0)
  if [ "${COUNT}" -ge "${NODE_THRESHOLD}" ]; then
    echo "[watcher] node count=${COUNT} >= ${NODE_THRESHOLD}, running install_calico()"
    install_calico || true
    touch "$LOCK"
    echo "[watcher] done"; exit 0
  fi
  sleep "${SLEEP_SEC}"
done
EOW
chmod +x /usr/local/bin/run-after-first-worker.sh

echo "[12] watcher systemd 서비스(비블로킹, 환경파일 사용)"
cat >/etc/systemd/system/after-first-worker.service <<'EOS'
[Unit]
Description=Run Calico install/patch after first worker joins
Wants=network-online.target
After=kubelet.service network-online.target

[Service]
Type=simple
Environment=KUBECONFIG=/etc/kubernetes/admin.conf
EnvironmentFile=/etc/cluster/env
ExecStart=/usr/local/bin/run-after-first-worker.sh
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOS

systemctl daemon-reload
systemctl enable --now after-first-worker.service

echo "[13] Helm 설치"
# 설치 디렉터리를 /usr/bin으로 강제해 PATH 문제 방지
export HELM_INSTALL_DIR=/usr/bin
curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash || true

# 혹시 스크립트가 /usr/local/bin에 깔았다면 링크로 보완
if [ -x /usr/local/bin/helm ] && [ ! -x /usr/bin/helm ]; then
  ln -sf /usr/local/bin/helm /usr/bin/helm
fi

# (선택) 플러그인 대비 git 설치
dnf -y install git || true

# 최종 확인(실패해도 프로비저닝 계속)
helm version || true

echo "[완료] join: http://${API_IP}:8000/join.sh"
echo "       워커가 조인되면 Calico가 자동으로 설치/패치됩니다."
