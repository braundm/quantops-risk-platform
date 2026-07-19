param(
    [Parameter(Position = 0, Mandatory = $true)]
    [ValidateSet(
        "doctor", "setup", "lint", "format", "format-check", "typecheck",
        "test", "test-unit", "test-integration", "test-contract", "test-e2e",
        "test-performance", "test-openapi", "event-test", "stream-test",
        "scheduler-test", "mcp-test", "ai-test", "ai-evaluate", "ml-test",
        "ml-train-demo", "ml-evaluate", "web-lint", "web-typecheck", "web-test",
        "web-build", "security", "security-scan", "dependency-audit", "docs-check",
        "migrate", "seed", "demo", "compose-check", "docker-build", "up", "down",
        "clean"
    )]
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

function Invoke-Uv {
    param([string[]]$Arguments)
    Invoke-Checked (Resolve-Uv) $Arguments
}

function Invoke-Pnpm {
    param([string[]]$Arguments)
    Invoke-Checked (Resolve-Pnpm) $Arguments
}

function Invoke-Pytest {
    param([string[]]$Arguments)
    Invoke-Uv (@("run", "pytest", "-p", "no:cacheprovider") + $Arguments)
}

function Invoke-EventTests {
    Invoke-Pytest @(
        "-c", "packages/data_contracts/pyproject.toml",
        "packages/data_contracts/tests"
    )
}

function Invoke-McpTests {
    Invoke-Pytest @("-c", "apps/mcp_server/pyproject.toml", "apps/mcp_server/tests")
}

function Invoke-MlEvaluation {
    Invoke-Uv @(
        "run", "python", "-m", "quantops_ml", "run",
        "--prices", "data/synthetic/canonical/price_bars.csv",
        "--manifest", "data/synthetic/manifest.json",
        "--output", "artifacts/ci/ml-demo"
    )
}

function Invoke-DependencyAudit {
    $ArtifactDirectory = Join-Path $ProjectRoot "artifacts\ci"
    New-Item -ItemType Directory -Path $ArtifactDirectory -Force | Out-Null
    Invoke-Uv @(
        "export", "--locked", "--all-packages", "--all-groups", "--no-emit-workspace",
        "--format", "requirements.txt",
        "--output-file", "artifacts/ci/python-requirements.txt"
    )
    Invoke-Uv @(
        "run", "pip-audit",
        "--requirement", "artifacts/ci/python-requirements.txt",
        "--require-hashes", "--strict"
    )
    Invoke-Uv @(
        "export", "--locked", "--all-packages", "--no-dev", "--no-emit-workspace",
        "--format", "cyclonedx1.5",
        "--output-file", "artifacts/ci/python-sbom.cdx.json"
    )
    Invoke-Pnpm @("audit", "--prod")
}

switch ($Command) {
    "doctor" { Invoke-Checked "python" @("scripts/doctor.py") }
    "setup" {
        Invoke-Uv @("sync", "--locked", "--all-packages", "--all-groups")
        Invoke-Pnpm @("install", "--frozen-lockfile")
    }
    "lint" {
        Invoke-Uv @("run", "ruff", "format", "--check", ".")
        Invoke-Uv @("run", "ruff", "check", ".")
        Invoke-Pnpm @("lint")
    }
    "format" {
        Invoke-Uv @("run", "ruff", "format", ".")
        Invoke-Uv @("run", "ruff", "check", "--fix", ".")
    }
    "format-check" { Invoke-Uv @("run", "ruff", "format", "--check", ".") }
    "typecheck" {
        Invoke-Uv @("run", "python", "scripts/typecheck.py")
        Invoke-Pnpm @("typecheck")
    }
    "test" {
        Invoke-Pytest @("-m", "not integration and not e2e")
        Invoke-EventTests
        Invoke-Pytest @("-c", "apps/stream_worker/pyproject.toml", "apps/stream_worker/tests")
        Invoke-Pytest @("-c", "apps/scheduler/pyproject.toml", "apps/scheduler/tests")
        Invoke-McpTests
        Invoke-Pytest @("-c", "packages/ai_engine/pyproject.toml", "packages/ai_engine/tests")
        Invoke-Pytest @("-c", "ml/pyproject.toml", "ml/tests")
        Invoke-Pnpm @("--filter", "@quantops/web", "test")
    }
    "test-unit" { Invoke-Pytest @("-m", "not integration and not e2e") }
    "test-integration" { Invoke-Pytest @("-m", "integration") }
    "test-contract" {
        Invoke-EventTests
        Invoke-McpTests
    }
    "test-e2e" { Invoke-Pnpm @("--filter", "@quantops/web", "test") }
    "test-performance" {
        Invoke-Uv @(
            "run", "python", "packages/risk_engine/benchmarks/benchmark_risk_engine.py"
        )
    }
    "test-openapi" {
        Invoke-Pytest @(
            "apps/api/tests/test_health.py::test_checked_in_openapi_snapshot_matches_application"
        )
    }
    "event-test" { Invoke-EventTests }
    "stream-test" {
        Invoke-Pytest @("-c", "apps/stream_worker/pyproject.toml", "apps/stream_worker/tests")
    }
    "scheduler-test" {
        Invoke-Pytest @("-c", "apps/scheduler/pyproject.toml", "apps/scheduler/tests")
    }
    "mcp-test" { Invoke-McpTests }
    "ai-test" {
        Invoke-Pytest @("-c", "packages/ai_engine/pyproject.toml", "packages/ai_engine/tests")
    }
    "ai-evaluate" {
        Invoke-Uv @(
            "run", "python", "-m", "quantops_ai", "evaluate",
            "--output", "artifacts/ci/ai-evaluation-report.json"
        )
    }
    "ml-test" { Invoke-Pytest @("-c", "ml/pyproject.toml", "ml/tests") }
    "ml-train-demo" { Invoke-MlEvaluation }
    "ml-evaluate" { Invoke-MlEvaluation }
    "web-lint" { Invoke-Pnpm @("--filter", "@quantops/web", "lint") }
    "web-typecheck" { Invoke-Pnpm @("--filter", "@quantops/web", "typecheck") }
    "web-test" { Invoke-Pnpm @("--filter", "@quantops/web", "test") }
    "web-build" { Invoke-Pnpm @("--filter", "@quantops/web", "build") }
    "security" {
        Invoke-Uv @("run", "python", "scripts/security_scan.py")
        Invoke-DependencyAudit
    }
    "security-scan" { Invoke-Uv @("run", "python", "scripts/security_scan.py") }
    "dependency-audit" { Invoke-DependencyAudit }
    "docs-check" { Invoke-Uv @("run", "python", "scripts/docs_check.py") }
    "migrate" { Invoke-Uv @("run", "alembic", "-c", "apps/api/alembic.ini", "upgrade", "head") }
    "seed" {
        Invoke-Uv @("run", "python", "-m", "quantops_pipelines", "generate")
        Invoke-Uv @(
            "run", "python", "-m", "quantops_pipelines", "verify",
            "--dataset", "data/synthetic"
        )
    }
    "demo" {
        Invoke-Checked "docker" @("compose", "up", "--build", "-d")
        Invoke-Uv @("run", "alembic", "-c", "apps/api/alembic.ini", "upgrade", "head")
        Invoke-Uv @("run", "python", "-m", "quantops_pipelines", "generate")
        Invoke-Uv @(
            "run", "python", "-m", "quantops_pipelines", "verify",
            "--dataset", "data/synthetic"
        )
        Write-Host "Web: http://localhost:5173  API: http://localhost:8000  Docs: http://localhost:8000/docs"
    }
    "compose-check" { Invoke-Checked "docker" @("compose", "config", "--quiet") }
    "docker-build" {
        Invoke-Checked "docker" @("compose", "config", "--quiet")
        Invoke-Checked "docker" @(
            "build", "--file", "apps/api/Dockerfile", "--tag", "quantops-api:local", "."
        )
        Invoke-Checked "docker" @(
            "build", "--file", "apps/web/Dockerfile", "--tag", "quantops-web:local", "."
        )
    }
    "up" { Invoke-Checked "docker" @("compose", "up", "--build", "-d") }
    "down" { Invoke-Checked "docker" @("compose", "down") }
    "clean" { Invoke-Uv @("run", "python", "scripts/clean.py") }
}
