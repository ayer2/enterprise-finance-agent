$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    docker compose config --quiet
    docker compose ps

    $frontendPort = if ($env:M7_FRONTEND_PORT) { $env:M7_FRONTEND_PORT } else { '3000' }
    $backendPort = if ($env:M7_BACKEND_PORT) { $env:M7_BACKEND_PORT } else { '8065' }

    Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$frontendPort/healthz" | Out-Null
    Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$backendPort/api/agent/list" | Out-Null

    docker compose exec -T database sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql --user=root --execute="source /validation/03_validation_queries.sql"'
    docker compose exec -T database sh -c 'MYSQL_PWD="$ENTERPRISE_DEMO_READONLY_PASSWORD" mysql --user=enterprise_agent_ro enterprise_demo --execute="SELECT COUNT(*) AS sales_order_count FROM sales_order"'

    docker compose exec -T database sh -c 'MYSQL_PWD="$ENTERPRISE_DEMO_READONLY_PASSWORD" mysql --user=enterprise_agent_ro enterprise_demo --execute="DELETE FROM sales_order WHERE id = -1"' 2>$null
    if ($LASTEXITCODE -eq 0) {
        throw 'Read-only account unexpectedly executed a write statement.'
    }

    Write-Host 'M7_DEPLOYMENT_VERIFICATION_PASSED'
}
finally {
    Pop-Location
}
