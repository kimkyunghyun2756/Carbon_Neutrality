#!/usr/bin/env bash
# PostgreSQL 설치 + 계정/DB 생성 + 방화벽/접속허용 설정
# 실행: root(또는 sudo 가능 계정)
exec > >(tee -a /var/log/provision-db.log) 2>&1
set -euo pipefail

# --- Vagrant env(없으면 기본값) ---
DB_IP="${DB_IP:-192.168.4.105}"
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

PGDATA="/var/lib/pgsql/${POSTGRES_VER}/data"
CONF="${PGDATA}/postgresql.conf"
HBA="${PGDATA}/pg_hba.conf"

echo "[2] initdb (이미 초기화된 경우 건너뜀)"
if [[ ! -s "${PGDATA}/PG_VERSION" ]]; then
  "/usr/pgsql-${POSTGRES_VER}/bin/postgresql-${POSTGRES_VER}-setup" initdb
else
  echo " - PGDATA already initialized, skipping initdb"
fi

echo "[3] 설정 수정(listen, port, encryption)"
sed -ri "s/^[#]*\s*listen_addresses\s*=.*/listen_addresses = '*'/" "$CONF"
sed -ri "s/^[#]*\s*port\s*=.*/port = ${DB_PORT}/" "$CONF"
grep -q '^password_encryption' "$CONF" \
  && sed -ri "s/^password_encryption\s*=.*/password_encryption = 'scram-sha-256'/" "$CONF" \
  || echo "password_encryption = 'scram-sha-256'" >> "$CONF"

echo "[4] 접속 허용(pg_hba.conf) - ${DB_NET_CIDR} (중복 방지)"
HBA_LINE_APP="host    ${APP_DB}    ${APP_USER}   ${DB_NET_CIDR}   scram-sha-256"
HBA_LINE_SUP="host    all          postgres      ${DB_NET_CIDR}   scram-sha-256"
grep -qF "${HBA_LINE_APP}" "$HBA" || echo "${HBA_LINE_APP}" >> "$HBA"
grep -qF "${HBA_LINE_SUP}" "$HBA" || echo "${HBA_LINE_SUP}" >> "$HBA"

echo "[5] 서비스 기동/재시작"
systemctl enable --now "postgresql-${POSTGRES_VER}"
systemctl restart "postgresql-${POSTGRES_VER}"

echo "[6] 계정/DB 생성 및 비밀번호 설정 (idempotent, \gexec 활용)"
sudo -u postgres psql -v ON_ERROR_STOP=1 \
  -v dbname="${APP_DB}" \
  -v owner="${APP_USER}" \
  -v apppass="${APP_PASS}" \
  -v pgpass="${POSTGRES_PASS}" \
  -d postgres <<'SQL'
\set ON_ERROR_STOP on

-- 6-1) postgres 슈퍼유저 비밀번호 설정
ALTER ROLE postgres WITH PASSWORD :'pgpass';

-- 6-2) 앱 ROLE이 없으면 생성 (조건부 + \gexec)
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'owner', :'apppass')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'owner');
\gexec

-- 존재하든 말든 비밀번호/LOGIN 보장
ALTER ROLE :"owner" WITH LOGIN PASSWORD :'apppass';

-- 6-3) DB가 없으면 생성 (조건부 + \gexec)
SELECT format('CREATE DATABASE %I OWNER %I', :'dbname', :'owner')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'dbname');
\gexec

-- 6-4) 권한/스키마 정리
\connect :dbname
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT  ALL ON SCHEMA public TO :"owner";
SQL

echo "[7] 방화벽 ${DB_PORT}/tcp 열기"
firewall-cmd --add-port=${DB_PORT}/tcp --permanent || true
firewall-cmd --reload || true

echo "[OK] PostgreSQL ${POSTGRES_VER} up @ ${DB_IP}:${DB_PORT}"
echo "     app DSN (psycopg/SQLAlchemy): postgresql+psycopg://${APP_USER}:${APP_PASS}@${DB_IP}:${DB_PORT}/${APP_DB}"
