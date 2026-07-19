param(
    [Parameter(Position = 0, Mandatory = $true)]
    [ValidateSet("doctor", "setup", "lint", "format", "typecheck", "test", "test-unit", "test-integration", "test-contract", "security", "docs-check", "up", "down")]
    [string]$Command
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $ProjectRoot

function Invoke-Checked {
    param([string]$Executable, [string[]]$Arguments)
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Executable exited with code $LASTEXITCODE"
    }
}

function Resolve-Uv {
    $UvCommand = Get-Command uv -ErrorAction SilentlyContinue
    if ($null -ne $UvCommand) { return $UvCommand.Source }
    $WorkspaceUv = Join-Path $ProjectRoot ".venv\Scripts\uv.exe"
    if (Test-Path -LiteralPath $WorkspaceUv) { return $WorkspaceUv }
    throw "uv was not found. Install it from https://docs.astral.sh/uv/."
}

function Resolve-Pnpm {
    $PnpmCommand = Get-Command pnpm -ErrorAction SilentlyContinue
    if ($null -ne $PnpmCommand) { return $PnpmCommand.Source }
    throw "pnpm was not found. Install the version declared in package.json."
}

switch ($Command) {
    "doctor" { Invoke-Checked "python" @("scripts/doctor.py") }
    "setup" {
        Invoke-Checked (Resolve-Uv) @("sync", "--all-packages")
        Invoke-Checked (Resolve-Pnpm) @("install", "--frozen-lockfile")
    }
    "lint" {
        Invoke-Checked (Resolve-Uv) @("run", "ruff", "check", ".")
        Invoke-Checked (Resolve-Pnpm) @("lint")
    }
    "format" {
        Invoke-Checked (Resolve-Uv) @("run", "ruff", "format", ".")
        Invoke-Checked (Resolve-Uv) @("run", "ruff", "check", "--fix", ".")
    }
    "typecheck" {
        Invoke-Checked (Resolve-Uv) @("run", "mypy", "apps", "packages", "pipelines", "ml")
        Invoke-Checked (Resolve-Pnpm) @("typecheck")
    }
    "test" { Invoke-Checked (Resolve-Uv) @("run", "pytest", "-m", "not integration and not e2e") }
    "test-unit" { Invoke-Checked (Resolve-Uv) @("run", "pytest", "-m", "not integration and not e2e") }
    "test-integration" { Invoke-Checked (Resolve-Uv) @("run", "pytest", "-m", "integration") }
    "test-contract" { Invoke-Checked (Resolve-Uv) @("run", "pytest", "-m", "contract") }
    "security" {
        Invoke-Checked (Resolve-Uv) @("run", "pip-audit")
        Invoke-Checked (Resolve-Pnpm) @("audit", "--prod")
    }
    "docs-check" { Invoke-Checked (Resolve-Uv) @("run", "python", "scripts/docs_check.py") }
    "up" { Invoke-Checked "docker" @("compose", "up", "--build", "-d") }
    "down" { Invoke-Checked "docker" @("compose", "down") }
}
