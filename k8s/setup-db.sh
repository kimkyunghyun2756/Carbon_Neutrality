#!/bin/bash
# PostgreSQL 외부 접속 설정 자동화 스크립트
# root 계정에서 실행해야 합니다.

# ----- Root 권한 체크 -----
if [ "$EUID" -ne 0 ]; then
          echo " 이 스크립트는 root 권한으로 실행해야 합니다."
            echo " sudo ./setup_postgres_remote.sh"
              exit 1
      fi

      # ----- PostgreSQL 설정 경로 -----
      # CentOS/RHEL 기준
      PG_CONF="/var/lib/pgsql/16/data/postgresql.conf"
      PG_HBA="/var/lib/pgsql/16/data/pg_hba.conf"

      # Ubuntu/Debian 계열은 아래처럼 바꿔야 할 수도 있음
      # PG_CONF="/etc/postgresql/14/main/postgresql.conf"
      # PG_HBA="/etc/postgresql/14/main/pg_hba.conf"

      echo "[1/4] postgresql.conf 수정 (listen_addresses)"
      if grep -q "^#listen_addresses" $PG_CONF; then
                  sed -i "s/^#listen_addresses.*/listen_addresses = '*'/" $PG_CONF
          elif grep -q "^listen_addresses" $PG_CONF; then
                      sed -i "s/^listen_addresses.*/listen_addresses = '*'/" $PG_CONF
              else
                          echo "listen_addresses = '*'" >> $PG_CONF
                  fi

                  echo "[2/4] pg_hba.conf 수정 (192.168.4.0/24 허용)"
                  if ! grep -q "192.168.4.0/24" $PG_HBA; then
                              echo "host    all             all             192.168.4.0/24            md5" >> $PG_HBA
                      fi

                      echo "[3/4] 방화벽 5432 포트 오픈"
                      firewall-cmd --add-port=5432/tcp --permanent
                      firewall-cmd --reload

                      echo "[4/4] PostgreSQL 재시작"
                      systemctl restart postgresql-16

                      echo " 완료!"
                      echo " 로컬 PC에서 접속 테스트:"
                      echo "   psql -h 192.168.4.105 -U app -d appdb"