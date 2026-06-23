<#
.SYNOPSIS
  StockFinRAG smoke-test driver.  Tests all three API endpoints.

.DESCRIPTION
  Connects to a running StockFinRAG API server (real or test) and exercises
  /api/health, /api/ask, and /api/ingest.  Reports PASS/FAIL per endpoint.

  If no server is running on :5000, this script auto-starts the minimal
  test stub (test_health.py) so it always works out of the box.

  Real mode (full app):
      cd StockFinRAG
      .\app\venv\Scripts\Activate.ps1
      docker compose up -d
      python app\api_server.py &
      .claude\skills\run-stockfinrag\driver.ps1

  Test mode (no Docker needed):
      cd StockFinRAG
      .\app\venv\Scripts\Activate.ps1
      python .claude\skills\run-stockfinrag\driver.ps1

.NOTES
  Written for the /run-stockfinrag skill.
#>

$ErrorActionPreference = "Stop"

$PASS_COUNT = 0
$FAIL_COUNT = 0
$API_HOST = "http://127.0.0.1:5000"
# ── Start test server if nothing is listening ─────────────────────────────
try {
    $null = Invoke-RestMethod -Uri "$API_HOST/api/health" -TimeoutSec 2 -ErrorAction Stop
    Write-Host "[driver] Using existing server at $API_HOST" -ForegroundColor Cyan
} catch {
    Write-Host "[driver] No server detected — starting test stub..." -ForegroundColor Yellow
    $testSrv = Join-Path $PSScriptRoot "test_health.py"
    if (-not (Test-Path $testSrv)) {
        Write-Host "FATAL: test stub not found at $testSrv" -ForegroundColor Red
        exit 1
    }
    $script:TEST_PID = (Start-Process -NoNewWindow -PassThru -FilePath python `
        -ArgumentList "-u", $testSrv).Id
    Start-Sleep -Seconds 3
    Write-Host "[driver] Test server started (PID $script:TEST_PID)" -ForegroundColor Cyan
}

# ── helpers ───────────────────────────────────────────────────────────────
function Test-Endpoint($name, $method, $url, $body, $expectKey) {
    try {
        if ($body) {
            $r = Invoke-RestMethod -Method $method -Uri $url `
                -ContentType "application/json" -Body ($body | ConvertTo-Json) `
                -TimeoutSec 15 -ErrorAction Stop
        } else {
            $r = Invoke-RestMethod -Method $method -Uri $url `
                -TimeoutSec 15 -ErrorAction Stop
        }
        if ($expectKey -and $null -eq $r.$expectKey) {
            Write-Host "FAIL  $name  --  missing key '$expectKey' in response" -ForegroundColor Red
            $script:FAIL_COUNT++
            return
        }
        $json = $r | ConvertTo-Json -Compress -Depth 2
        $preview = $json.Substring(0, [Math]::Min(120, $json.Length))
        Write-Host "PASS  $name  --  $preview" -ForegroundColor Green
        $script:PASS_COUNT++
    } catch {
        Write-Host "FAIL  $name  --  $_" -ForegroundColor Red
        $script:FAIL_COUNT++
    }
}

# ── tests ─────────────────────────────────────────────────────────────────
Write-Host "`n========== StockFinRAG Smoke Test ==========" -ForegroundColor Cyan
Write-Host "Target: $API_HOST`n" -ForegroundColor Cyan

Test-Endpoint -name "GET /api/health" -method GET -url "$API_HOST/api/health" -expectKey "status"

Test-Endpoint -name "POST /api/ask" -method POST -url "$API_HOST/api/ask" `
    -body @{question="2024年银行板块表现如何？"} -expectKey "answer"

Test-Endpoint -name "POST /api/ingest" -method POST -url "$API_HOST/api/ingest" `
    -body @{limit=5} -expectKey "status"

# ── summary ───────────────────────────────────────────────────────────────
Write-Host "`n========== Results  $PASS_COUNT passed, $FAIL_COUNT failed ==========" -ForegroundColor Cyan

if ($TEST_PID) {
    Stop-Process -Id $TEST_PID -Force -ErrorAction SilentlyContinue
    Write-Host "[driver] Test server stopped" -ForegroundColor Cyan
}

if ($FAIL_COUNT -gt 0) { exit 1 }
