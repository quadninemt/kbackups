param(
    [ValidateSet("weekly", "monthly", "both")]
    [string]$Mode = "both",

    [switch]$KeepTasks
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

function Get-PythonExecutable {
    $candidates = @(
        ".\\venv\\Scripts\\python.exe",
        ".\\.venv\\Scripts\\python.exe"
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return (Resolve-Path $candidate).Path
        }
    }

    return "python"
}

function Invoke-PythonCode {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PythonExe,

        [Parameter(Mandatory = $true)]
        [string]$Code,

        [Parameter(Mandatory = $true)]
        [string]$ExpectToken,

        [Parameter(Mandatory = $true)]
        [string]$StepName
    )

    $encodedCode = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($Code))
    $bootstrap = "import base64; exec(base64.b64decode('$encodedCode').decode('utf-8'))"

    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & $PythonExe -c $bootstrap 2>&1 | Out-String
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }

    if ($LASTEXITCODE -ne 0) {
        throw "${StepName} failed (python exit code $LASTEXITCODE). Output:`n$output"
    }

    if ($output -notmatch [regex]::Escape($ExpectToken)) {
        throw "${StepName} did not return expected token '$ExpectToken'. Output:`n$output"
    }

    return $output
}

function Remove-TaskIfExists {
    param([string]$TaskName)

    & cmd.exe /c "schtasks /Delete /F /TN `"$TaskName`" >nul 2>nul" | Out-Null
}

function Get-TaskSummary {
    param([string]$TaskName)

    $query = & cmd.exe /c "schtasks /Query /TN `"$TaskName`" /FO LIST /V" 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) {
        return $query
    }

    return ($query | Select-String "TaskName:|Status:|Scheduled Task State:|Next Run Time:|Schedule Type:" -CaseSensitive:$false | Out-String)
}

function Test-ScheduleFlow {
    param(
        [string]$PythonExe,
        [string]$TaskName,
        [string]$Recurrence,
        [string]$Time,
        [string]$DayOfWeek,
        [string]$DayOfMonth,
        [string]$Message,
        [switch]$KeepTask
    )

    Write-Host "--- Testing $Recurrence schedule ($TaskName) ---" -ForegroundColor Cyan
    Remove-TaskIfExists -TaskName $TaskName

    $createCode = @"
from src.scheduler_manager import SchedulerManager
sm = SchedulerManager()
print("create_ok=", sm.create_or_update_reminder(task_name=r"$TaskName", recurrence=r"$Recurrence", run_time=r"$Time", reminder_message=r"$Message", day_of_week=r"$DayOfWeek", day_of_month=r"$DayOfMonth"))
"@

    $createOutput = Invoke-PythonCode -PythonExe $PythonExe -Code $createCode -ExpectToken "create_ok= True" -StepName "Create $Recurrence"
    Write-Host ($createOutput.Trim())
    Write-Host (Get-TaskSummary -TaskName $TaskName)

    $disableCode = @"
from src.scheduler_manager import SchedulerManager
sm = SchedulerManager()
print("disable_ok=", sm.set_task_enabled(r"$TaskName", False))
"@

    $disableOutput = Invoke-PythonCode -PythonExe $PythonExe -Code $disableCode -ExpectToken "disable_ok= True" -StepName "Disable $Recurrence"
    Write-Host ($disableOutput.Trim())
    Write-Host (Get-TaskSummary -TaskName $TaskName)

    if ($KeepTask) {
        Write-Host "Keeping task '$TaskName' as requested." -ForegroundColor Yellow
        return
    }

    $removeCode = @"
from src.scheduler_manager import SchedulerManager
sm = SchedulerManager()
print("remove_ok=", sm.remove_reminder(r"$TaskName"))
"@

    $removeOutput = Invoke-PythonCode -PythonExe $PythonExe -Code $removeCode -ExpectToken "remove_ok= True" -StepName "Remove $Recurrence"
    Write-Host ($removeOutput.Trim())

    $postRemoveQuery = & cmd.exe /c "schtasks /Query /TN `"$TaskName`" 2>nul" | Out-String
    if ($LASTEXITCODE -eq 0) {
        throw "Task '$TaskName' still exists after remove step."
    }

    Write-Host "Task '$TaskName' removed successfully." -ForegroundColor Green
}

$pythonExe = Get-PythonExecutable
Write-Host "Using Python: $pythonExe"

if ($Mode -in @("weekly", "both")) {
    $weeklyParams = @{
        PythonExe  = $pythonExe
        TaskName   = "k_backups_schedule_smoke_weekly"
        Recurrence = "Weekly"
        Time       = "09:00"
        DayOfWeek  = "Monday"
        DayOfMonth = "1"
        Message    = "k_backups weekly schedule smoke test"
        KeepTask   = [bool]$KeepTasks
    }
    Test-ScheduleFlow @weeklyParams
}

if ($Mode -in @("monthly", "both")) {
    $monthlyParams = @{
        PythonExe  = $pythonExe
        TaskName   = "k_backups_schedule_smoke_monthly"
        Recurrence = "Monthly"
        Time       = "10:30"
        DayOfWeek  = "Monday"
        DayOfMonth = "15"
        Message    = "k_backups monthly schedule smoke test"
        KeepTask   = [bool]$KeepTasks
    }
    Test-ScheduleFlow @monthlyParams
}

Write-Host "Schedule smoke test completed successfully." -ForegroundColor Green
