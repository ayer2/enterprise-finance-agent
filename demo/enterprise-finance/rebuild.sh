#!/usr/bin/env bash
set -euo pipefail

demo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python "$demo_root/generator/generate.py"
python -m unittest discover -s "$demo_root/generator" -p 'test_*.py'

if [[ "${1:-}" == "--skip-docker" ]]; then
  echo "Generation and deterministic checks passed; Docker rebuild skipped."
  exit 0
fi

if [[ -z "${ENTERPRISE_DEMO_ROOT_PASSWORD:-}" ]]; then
  ENTERPRISE_DEMO_ROOT_PASSWORD="$(python -c 'import secrets; print(secrets.token_hex(16))')"
  export ENTERPRISE_DEMO_ROOT_PASSWORD
fi
if [[ -z "${ENTERPRISE_DEMO_READONLY_PASSWORD:-}" ]]; then
  ENTERPRISE_DEMO_READONLY_PASSWORD="$(python -c 'import secrets; print(secrets.token_hex(16))')"
  export ENTERPRISE_DEMO_READONLY_PASSWORD
fi
if [[ ! "$ENTERPRISE_DEMO_READONLY_PASSWORD" =~ ^[A-Za-z0-9._~-]{16,128}$ ]]; then
  echo "ENTERPRISE_DEMO_READONLY_PASSWORD must contain 16-128 safe ASCII characters." >&2
  exit 1
fi

docker compose -f "$demo_root/docker-compose.yml" down --volumes --remove-orphans
docker compose -f "$demo_root/docker-compose.yml" up -d --wait
docker compose -f "$demo_root/docker-compose.yml" exec -T \
  -e MYSQL_PWD="$ENTERPRISE_DEMO_ROOT_PASSWORD" mysql \
  mysql --user=root --execute='source /validation/03_validation_queries.sql'

docker compose -f "$demo_root/docker-compose.yml" exec -T \
  -e MYSQL_PWD="$ENTERPRISE_DEMO_READONLY_PASSWORD" mysql \
  mysql enterprise_demo --user=enterprise_agent_ro --execute='SELECT COUNT(*) FROM sales_order'

if docker compose -f "$demo_root/docker-compose.yml" exec -T \
  -e MYSQL_PWD="$ENTERPRISE_DEMO_READONLY_PASSWORD" mysql \
  mysql enterprise_demo --user=enterprise_agent_ro --execute='DELETE FROM sales_order WHERE id = -1'; then
  echo "Read-only account unexpectedly executed a write statement." >&2
  exit 1
fi

echo "enterprise_demo rebuilt; deterministic checks and read-only permission checks passed on 127.0.0.1:3307."
