param(
    [switch]$CheckOnly,
    [switch]$UpgradeOnly
)

if ($CheckOnly -and $UpgradeOnly) {
    throw 'Choose either -CheckOnly or -UpgradeOnly'
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $repoRoot '.env'
$databaseLine = Get-Content -LiteralPath $envFile | Where-Object { $_ -match '^DATABASE_URL=' } | Select-Object -First 1
if (-not $databaseLine) {
    throw 'DATABASE_URL is missing from .env'
}

$sourceUrl = ($databaseLine -split '=', 2)[1].Trim().Trim('"', "'")
$sourceUri = [Uri]$sourceUrl
if ($sourceUri.Host -notin @('localhost', '127.0.0.1')) {
    throw 'This helper only accepts a local PostgreSQL server'
}
$builder = [UriBuilder]::new($sourceUri)
$builder.Path = '/mumtmis_legacy_import_full_dev'
$env:DATABASE_URL = $builder.Uri.AbsoluteUri
$env:FLASK_APP = 'app.main:app'

Write-Host 'Test database: mumtmis_legacy_import_full_dev (localhost)'
if ($CheckOnly) {
    return
}

Push-Location $repoRoot
try {
    if ($UpgradeOnly) {
        flask db upgrade
    } else {
        flask run
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Flask exited with code $LASTEXITCODE"
    }
} finally {
    Pop-Location
}
