# Interactive Windows-only secret entry. The key is never written to this repo.
$ErrorActionPreference = 'Stop'
$Host.UI.RawUI.WindowTitle = 'Roofscapes - Connect Google Stitch'
Write-Host 'Connect Google Stitch to Codex' -ForegroundColor Green
Write-Host '1. Sign in to Stitch and create an API key under Settings > API Keys.'
Write-Host '2. Paste the key below. Input is masked. Do not paste it into chat.'
Write-Host 'The key is encrypted with Windows DPAPI for your Windows user.'
Write-Host 'It is stored under your local AppData, outside the repository.'
Write-Host 'After verification, this will create the requested Research Studio project.'
Write-Host ''
$stitchSecret = Read-Host 'Stitch API key (Enter to cancel)' -AsSecureString
if ($stitchSecret.Length -eq 0) { Write-Host 'Cancelled; no credential stored.'; exit 0 }
$credentialDirectory = Join-Path $env:LOCALAPPDATA 'Roofscapes\Stitch'
New-Item -ItemType Directory -Path $credentialDirectory -Force | Out-Null
$credential = New-Object System.Management.Automation.PSCredential ('stitch', $stitchSecret)
$credential | Export-Clixml -LiteralPath (Join-Path $credentialDirectory 'credential.xml')
$workspaceRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location -LiteralPath $workspaceRoot
& (Join-Path $workspaceRoot '.venv\Scripts\python.exe') -m ui.integrations.stitch --create-project
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Authentication was not verified. Re-run this setup with a valid Stitch key.' -ForegroundColor Yellow
    exit $LASTEXITCODE
}
Write-Host 'Stitch verified. Restart the Codex extension when ready to load its tools.' -ForegroundColor Green
