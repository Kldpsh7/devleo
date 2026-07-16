$ErrorActionPreference = "Stop"

$PackageSpec = if ($env:LEO_PACKAGE_SPEC) { $env:LEO_PACKAGE_SPEC } else { "lion-cub-pet" }
$Autostart = if ($env:LEO_AUTOSTART) { $env:LEO_AUTOSTART } else { "1" }

function Find-Uv {
    $Command = Get-Command uv -ErrorAction SilentlyContinue
    if ($Command) { return $Command.Source }

    $Candidates = @(
        (Join-Path $HOME ".local\bin\uv.exe"),
        (Join-Path $HOME ".cargo\bin\uv.exe")
    )
    foreach ($Candidate in $Candidates) {
        if (Test-Path $Candidate) { return $Candidate }
    }
    return $null
}

$Uv = Find-Uv
if (-not $Uv) {
    powershell -ExecutionPolicy ByPass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    $Uv = Find-Uv
    if (-not $Uv) { throw "uv installed but its executable could not be located" }
}

& $Uv tool install --force $PackageSpec
$ToolBin = (& $Uv tool dir --bin).Trim()
$Leo = Join-Path $ToolBin "lion-cub-pet.exe"

if ($Autostart -eq "0") {
    & $Leo install --start
} else {
    & $Leo install --autostart --start
}

Write-Host "Leo the Dev is installed and running."
