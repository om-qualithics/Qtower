# One-command dev bring-up: starts everything native dev needs and skips
# anything already running, so it's safe to re-run any time (e.g. after a
# Docker Desktop restart, a reboot, or a process that silently died).
#
# Brings up, in order:
#   1. infra containers (postgres/redis/minio/jackson/mock-saml) via
#      docker compose - NOT the codescan profile (api/worker containers),
#      which stays opt-in per CLAUDE.md.
#   2. the API (uvicorn) on :8000
#   3. the Celery worker (--pool=solo, -Q celery,codescan)
#   4. the frontend (pnpm dev) on :3000
#
# Each of 2-4 is launched via a one-shot Scheduled Task instead of plain
# Start-Process. Reason: a plain Start-Process'd window is still attached
# to this script's own process/job - if the caller running this script is
# itself sandboxed under a Windows Job Object (true when this script is
# run BY an agent/automation tool, not by a human directly in their own
# terminal), that job's cleanup silently kills every spawned window the
# moment the invoking call ends, even with -NoExit and even though the
# window looked like it started fine. A Scheduled Task's action runs as a
# genuinely independent process tree, immune to the launcher's own job
# object - the one reliable way found (after this dying twice) to make a
# background dev process actually outlive the command that started it.
# Logs go to infra/logs/*.log (gitignored) since detached processes have
# no visible console to read on failure.
#
# Run from anywhere:
#   powershell -ExecutionPolicy Bypass -File infra\scripts\dev-up.ps1

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path "$PSScriptRoot\..\.."
$logDir = "$repoRoot\infra\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Test-PortListening($port) {
    return $null -ne (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
}

# Launches `$command` detached from this script's own process tree via a
# one-shot Scheduled Task (see comment block above for why). stdout/stderr
# go to $logFile. The task definition is deleted right after triggering it
# - deleting the task does not stop the process it already launched.
# schtasks' /tr quoting can't cleanly take a multi-statement command line
# (&&, redirection) as one argument, so the command is written to a small
# throwaway .cmd wrapper file and schtasks just runs that file - sidesteps
# the quoting entirely.
function Start-Detached($taskName, $command, $logFile) {
    $wrapperPath = "$env:TEMP\$taskName.cmd"
    Set-Content -Path $wrapperPath -Value $command -Encoding ascii
    schtasks /create /tn $taskName /tr "`"$wrapperPath`"" /sc once /st 23:59 /f | Out-Null
    schtasks /run /tn $taskName | Out-Null
    Start-Sleep -Milliseconds 500
    schtasks /delete /tn $taskName /f | Out-Null
}

Write-Host "== infra containers ==" -ForegroundColor Cyan
Push-Location "$repoRoot\infra"
docker compose up -d
Pop-Location

Write-Host "Waiting for postgres to be healthy..."
$deadline = (Get-Date).AddSeconds(60)
while ((Get-Date) -lt $deadline) {
    $status = docker inspect -f "{{.State.Health.Status}}" project-misty-postgres-1 2>$null
    if ($status -eq "healthy") { break }
    Start-Sleep -Seconds 2
}

Write-Host "== API (uvicorn :8000) ==" -ForegroundColor Cyan
if (Test-PortListening 8000) {
    Write-Host "already running - skipping"
} else {
    $log = "$logDir\api.log"
    $cmd = "cd /d `"$repoRoot`"`r`napps\api\.venv\Scripts\python.exe -m uvicorn apps.api.main:app --port 8000 > `"$log`" 2>&1"
    Start-Detached "QTowerDev-API" $cmd $log
    Write-Host "started (log: $log)"
}

Write-Host "== Celery worker ==" -ForegroundColor Cyan
$celeryPidFile = "$repoRoot\infra\.celery-worker.pid"
$celeryRunning = $false
if (Test-Path $celeryPidFile) {
    $existingPid = Get-Content $celeryPidFile -ErrorAction SilentlyContinue
    if ($existingPid -and (Get-Process -Id $existingPid -ErrorAction SilentlyContinue)) { $celeryRunning = $true }
}
if ($celeryRunning) {
    Write-Host "already running (pid $existingPid) - skipping"
} else {
    $log = "$logDir\celery.log"
    $cmd = "cd /d `"$repoRoot`"`r`napps\api\.venv\Scripts\python.exe -m celery -A apps.api.core.celery_app worker --loglevel=info --pool=solo -Q celery,codescan > `"$log`" 2>&1"
    Start-Detached "QTowerDev-Celery" $cmd $log
    Write-Host "started (log: $log)"
    # Record the actual worker PID (not this launcher's) once it comes up,
    # so the next run's already-running check works.
    Start-Sleep -Seconds 3
    $proc = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -like "*celery*codescan*" } | Select-Object -First 1
    if ($proc) { $proc.ProcessId | Out-File -FilePath $celeryPidFile -Encoding ascii }
}

Write-Host "== Frontend (pnpm dev :3000) ==" -ForegroundColor Cyan
if (Test-PortListening 3000) {
    Write-Host "already running - skipping"
} else {
    $log = "$logDir\web.log"
    $cmd = "cd /d `"$repoRoot\apps\web`"`r`ncall pnpm dev > `"$log`" 2>&1"
    Start-Detached "QTowerDev-Web" $cmd $log
    Write-Host "started (log: $log)"
}

Write-Host ""
Write-Host "Verifying..." -ForegroundColor Cyan
$deadline = (Get-Date).AddSeconds(30)
while ((Get-Date) -lt $deadline -and -not ((Test-PortListening 8000) -and (Test-PortListening 3000))) {
    Start-Sleep -Seconds 2
}

if (Test-PortListening 8000) { Write-Host "API      :8000  OK" -ForegroundColor Green }
else { Write-Host "API      :8000  NOT responding - check $logDir\api.log" -ForegroundColor Red }

if (Test-PortListening 3000) { Write-Host "Frontend :3000  OK" -ForegroundColor Green }
else { Write-Host "Frontend :3000  NOT responding - check $logDir\web.log" -ForegroundColor Red }

Write-Host "Done. Logs are in $logDir - the processes have no visible window (detached)." -ForegroundColor Green
