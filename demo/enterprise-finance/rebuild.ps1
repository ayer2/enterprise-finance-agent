param(
    [switch]$SkipDocker
)

$ErrorActionPreference = 'Stop'
$demoRoot = $PSScriptRoot
$generator = Join-Path $demoRoot 'generator/generate.py'
$composeFile = Join-Path $demoRoot 'docker-compose.yml'

python $generator
if ($LASTEXITCODE -ne 0) {
    throw 'Synthetic data generation failed.'
}

python -m unittest discover -s (Join-Path $demoRoot 'generator') -p 'test_*.py'
if ($LASTEXITCODE -ne 0) {
    throw 'Synthetic data tests failed.'
}

if ($SkipDocker) {
    Write-Host 'Generation and deterministic checks passed; Docker rebuild skipped.'
    exit 0
}

if (-not $env:ENTERPRISE_DEMO_ROOT_PASSWORD) {
    $env:ENTERPRISE_DEMO_ROOT_PASSWORD = [Guid]::NewGuid().ToString('N')
}
if (-not $env:ENTERPRISE_DEMO_READONLY_PASSWORD) {
    $env:ENTERPRISE_DEMO_READONLY_PASSWORD = [Guid]::NewGuid().ToString('N')
}
if ($env:ENTERPRISE_DEMO_READONLY_PASSWORD -notmatch '^[A-Za-z0-9._~-]{16,128}$') {
    throw 'ENTERPRISE_DEMO_READONLY_PASSWORD must contain 16-128 safe ASCII characters.'
}

docker compose -f $composeFile down --volumes --remove-orphans
if ($LASTEXITCODE -ne 0) {
    throw 'Unable to reset the enterprise demo MySQL container.'
}

docker compose -f $composeFile up -d --wait
if ($LASTEXITCODE -ne 0) {
    throw 'Enterprise demo MySQL failed to become healthy.'
}

docker compose -f $composeFile exec -T -e MYSQL_PWD=$env:ENTERPRISE_DEMO_ROOT_PASSWORD mysql `
    mysql --user=root --execute='source /validation/03_validation_queries.sql'
if ($LASTEXITCODE -ne 0) {
    throw 'MySQL validation queries failed.'
}

docker compose -f $composeFile exec -T -e MYSQL_PWD=$env:ENTERPRISE_DEMO_READONLY_PASSWORD mysql mysql `
    enterprise_demo --user=enterprise_agent_ro --execute='SELECT COUNT(*) FROM sales_order'
if ($LASTEXITCODE -ne 0) {
    throw 'Read-only account could not execute SELECT.'
}

	$readonlyWriteOutput = docker compose -f $composeFile exec -T `
	    -e MYSQL_PWD=$env:ENTERPRISE_DEMO_READONLY_PASSWORD mysql mysql `
    enterprise_demo --user=enterprise_agent_ro --execute='DELETE FROM sales_order WHERE id = -1' 2>&1
if ($LASTEXITCODE -eq 0) {
    throw 'Read-only account unexpectedly executed a write statement.'
}

Write-Host 'enterprise_demo rebuilt; deterministic checks and read-only permission checks passed on 127.0.0.1:3307.'
