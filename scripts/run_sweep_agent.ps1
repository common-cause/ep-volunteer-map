# Volunteer-map training sweep, twice daily - invoked by Windows Task Scheduler
# ("EP Volunteer Map - training sweep agent", daily 06:00 and 14:00 local).
# One agent pass, dispatched THROUGH THE TOWER. Output lands in
# logs\sweep_agent\<timestamp>.log (gitignored, newest 60 kept).
# NOTE: keep this file pure ASCII - PS 5.1 reads BOM-less files as ANSI.
#
# WHY THESE SLOTS (contract .claude\dispatch.yaml -> schedule):
#   23:00 / 11:00  ep-training-map  publishes the public training payload
#   06:00 / 14:00  THIS             training-map-sweep (via the tower) -> Sheet rows
#   07:00 / 15:00  Civis            EP Volunteer Map Sync -> Pages
#
# THIS SCRIPT IS THE VEHICLE, NOT THE DISPATCHER (pattern lifted from
# ep-training-map\scripts\run_nightly_publish.ps1). The tower does freeze
# consult, grant gate, brief, spawn, ledger, tier-M/S. The spawned agent follows
# .claude\skills\training-map-sweep\SKILL.md.
#
# Do NOT "simplify" this to running scripts\sweep_apply.py or `claude -p`
# directly. Either bypasses the tower (treaty 2.8): no freeze, no grant check,
# no verification of public copy, no track record. A tower-side refusal,
# including "no catalog grant", means no sweep this slot, and Civis simply
# republishes the Sheet as it stands. There is deliberately no fallback path.

$ErrorActionPreference = 'Continue'

$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

$taskType = 'training-map-sweep'

$proj   = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $proj 'logs\sweep_agent'
New-Item -ItemType Directory -Force $logDir | Out-Null
$log    = Join-Path $logDir ((Get-Date -Format 'yyyy-MM-dd_HHmm') + '.log')

Set-Location $proj

$tower = $env:TOWER_ROOT
if (-not $tower) {
    $tower = Join-Path $env:USERPROFILE 'OneDrive - Common Cause Education Fund\Documents\Local AI Tools\RobAssistant'
}
$towerPy = $env:ASSISTANT_PYTHON
if (-not $towerPy) { $towerPy = 'C:\venvs\rob-assistant\Scripts\python.exe' }
$fire = Join-Path $tower 'scripts\dispatch_fire.py'

if (-not (Test-Path $fire)) {
    "=== TOWER MISSING at $fire - nothing dispatched this slot ===" |
        Out-File -Append -Encoding utf8 $log
    exit 1
}

"=== dispatch ep-volunteer-map :: $taskType - $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" |
    Out-File -Append -Encoding utf8 $log

& $towerPy $fire 'ep-volunteer-map' $taskType 2>&1 |
    ForEach-Object { $_.ToString() } |
    Out-File -Append -Encoding utf8 $log
$code = $LASTEXITCODE

"--- exit=$code at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ---" |
    Out-File -Append -Encoding utf8 $log

Get-ChildItem $logDir -Filter *.log |
    Sort-Object Name -Descending |
    Select-Object -Skip 60 |
    Remove-Item -Force

exit $code
