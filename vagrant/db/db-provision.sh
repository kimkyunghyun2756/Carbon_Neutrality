#!/usr/bin/env bash
# PostgreSQL 설치 + 계정/DB 생성 + 방화벽/접속허용 설정
exec > >(tee -a /var/log/provision-db.log) 2>&1
set -euo pipefail

# --- Vagrant env(없으면 기본값) ---
DB_IP="${DB_IP:-192.168.4.205}"
DB_PORT="${DB_PORT:-5432}"
DB_NET_CIDR="${DB_NET_CIDR:-192.168.4.0/24}"
POSTGRES_VER="${POSTGRES_VER:-16}"
POSTGRES_PASS="${POSTGRES_PASS:-root}"
APP_DB="${APP_DB:-appdb}"
APP_USER="${APP_USER:-app}"
APP_PASS="${APP_PASS:-apppw}"

# 영구 보관(참조용)
install -d /etc/cluster
cat >/etc/cluster/env <<EOF
DB_IP=${DB_IP}
DB_PORT=${DB_PORT}
DB_NET_CIDR=${DB_NET_CIDR}
POSTGRES_VER=${POSTGRES_VER}
APP_DB=${APP_DB}
APP_USER=${APP_USER}
EOF

echo "[0] 기본 패키지 및 방화벽"
dnf -y install dnf-plugins-core curl ca-certificates firewalld policycoreutils-python-utils || true
systemctl enable --now firewalld || true

echo "[1] PostgreSQL ${POSTGRES_VER} 설치(PGDG)"
dnf -y install https://download.postgresql.org/pub/repos/yum/reporpms/EL-8-x86_64/pgdg-redhat-repo-latest.noarch.rpm
dnf -qy module disable postgresql
PKG_VER="${POSTGRES_VER//./}"
dnf -y install "postgresql${PKG_VER}-server" "postgresql${PKG_VER}"

echo "[2] initdb"
"/usr/pgsql-${POSTGRES_VER}/bin/postgresql-${POSTGRES_VER}-setup" initdb

PGDATA="/var/lib/pgsql/${POSTGRES_VER}/data"
CONF="${PGDATA}/postgresql.conf"
HBA="${PGDATA}/pg_hba.conf"

echo "[3] 설정 수정(listen, port, encryption)"
sed -ri "s/^[#]*\s*listen_addresses\s*=.*/listen_addresses = '*'/" "$CONF"
sed -ri "s/^[#]*\s*port\s*=.*/port = ${DB_PORT}/" "$CONF"
grep -q '^password_encryption' "$CONF" \
  && sed -ri "s/^password_encryption\s*=.*/password_encryption = 'scram-sha-256'/" "$CONF" \
  || echo "password_encryption = 'scram-sha-256'" >> "$CONF"

echo "[4] 접속 허용(pg_hba.conf) - ${DB_NET_CIDR}"
cat >> "$HBA" <<EOF
# Vagrant added
host    ${APP_DB}    ${APP_USER}   ${DB_NET_CIDR}   scram-sha-256
# (옵션) postgres 슈퍼유저도 같은 대역에서 허용
host    all          postgres      ${DB_NET_CIDR}   scram-sha-256
EOF

echo "[5] 서비스 기동"
systemctl enable --now "postgresql-${POSTGRES_VER}"

echo "[6] 계정/DB 생성 및 비밀번호 설정"
sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
ALTER USER postgres WITH PASSWORD '${POSTGRES_PASS}';
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='${APP_USER}') THEN
     CREATE ROLE ${APP_USER} WITH LOGIN PASSWORD '${APP_PASS}';
  END IF;
END
\$\$;
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_database WHERE datname='${APP_DB}') THEN
     CREATE DATABASE ${APP_DB} OWNER ${APP_USER};
  END IF;
END
\$\$;
SQL

echo "[7] 방화벽 5432 열기"
firewall-cmd --add-port=${DB_PORT}/tcp --permanent || true
firewall-cmd --reload || true

echo "[OK] PostgreSQL ${POSTGRES_VER} up @ ${DB_IP}:${DB_PORT}"
echo "     app DSN (psycopg/SQLAlchemy): postgresql+psycopg://${APP_USER}:${APP_PASS}@${DB_IP}:${DB_PORT}/${APP_DB}"
