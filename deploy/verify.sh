#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

docker compose config --quiet
docker compose ps

frontend_port="$(docker compose port frontend 8080 | head -n 1 | sed 's/.*://')"
backend_port="$(docker compose port backend 8065 | head -n 1 | sed 's/.*://')"

curl --fail --silent --show-error "http://127.0.0.1:${frontend_port}/healthz" >/dev/null
curl --fail --silent --show-error "http://127.0.0.1:${backend_port}/api/agent/list" >/dev/null

docker compose exec -T database sh -c \
  'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql --user=root --execute="source /validation/03_validation_queries.sql"'

docker compose exec -T database sh -c \
  'MYSQL_PWD="$ENTERPRISE_DEMO_READONLY_PASSWORD" mysql --user=enterprise_agent_ro enterprise_demo --execute="SELECT COUNT(*) AS sales_order_count FROM sales_order"'

if docker compose exec -T database sh -c \
  'MYSQL_PWD="$ENTERPRISE_DEMO_READONLY_PASSWORD" mysql --user=enterprise_agent_ro enterprise_demo --execute="DELETE FROM sales_order WHERE id = -1"' \
  >/dev/null 2>&1; then
  echo 'Read-only account unexpectedly executed a write statement.' >&2
  exit 1
fi

echo 'M7_DEPLOYMENT_VERIFICATION_PASSED'
