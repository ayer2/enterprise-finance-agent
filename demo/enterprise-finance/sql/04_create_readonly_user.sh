#!/usr/bin/env bash
set -euo pipefail

if [[ ! "${ENTERPRISE_DEMO_READONLY_PASSWORD:-}" =~ ^[A-Za-z0-9._~-]{16,128}$ ]]; then
  echo "ENTERPRISE_DEMO_READONLY_PASSWORD must contain 16-128 safe ASCII characters." >&2
  exit 1
fi

MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql --protocol=socket --user=root <<SQL
CREATE USER IF NOT EXISTS 'enterprise_agent_ro'@'%' IDENTIFIED BY '${ENTERPRISE_DEMO_READONLY_PASSWORD}';
ALTER USER 'enterprise_agent_ro'@'%' IDENTIFIED BY '${ENTERPRISE_DEMO_READONLY_PASSWORD}';
REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'enterprise_agent_ro'@'%';
GRANT SELECT ON enterprise_demo.* TO 'enterprise_agent_ro'@'%';
FLUSH PRIVILEGES;
SQL
