# Codex calls this helper internally. Never run it in a shared/logged terminal.
$ErrorActionPreference = 'Stop'
$credentialPath = Join-Path $env:LOCALAPPDATA 'Roofscapes\Stitch\credential.xml'
if (-not (Test-Path -LiteralPath $credentialPath)) {
    Write-Output '{}'
    exit 0
}
$credential = Import-Clixml -LiteralPath $credentialPath
$headers = @{ 'X-Goog-Api-Key' = $credential.GetNetworkCredential().Password }
$headers | ConvertTo-Json -Compress
