#!/usr/bin/env pwsh
# Test-AllPythons.ps1
# ------------------------------------------------------------
# Run test suite against every supported Python version

$PythonVersions = @("3.10", "3.11", "3.12", "3.13", "3.14")
$PytestArgs = "-ra"

# ---- 3. Loop -------------------------------------------------------
foreach ($py in $PythonVersions) {
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host "Testing with Python $py" -ForegroundColor Cyan
    Write-Host "========================================`n" -ForegroundColor Cyan
    uv run --python $py --group dev --with-editable . pytest $PytestArgs

    if ($LASTEXITCODE -ne 0) {
        Write-Error "Tests failed on Python $py"
        exit $LASTEXITCODE
    }
}

Write-Host "`nAll Python versions passed." -ForegroundColor Green
