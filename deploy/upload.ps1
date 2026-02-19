# Sube variables de entorno y config al servidor 104.248.177.53
# Requiere: PuTTY (plink, pscp) en el PATH, o que ejecutes desde Git Bash con sshpass
# Uso: .\deploy\upload.ps1

$ErrorActionPreference = "Stop"
$Server = "104.248.177.53"
$User = "root"
$RemotePath = "/var/www/restaurant_reports"
$ProjectRoot = Join-Path $PSScriptRoot ".."

$SecretFile = Join-Path $PSScriptRoot "server.secret"
if (-not (Test-Path $SecretFile)) {
    Write-Host "Crea deploy/server.secret con una sola linea: la contraseña del servidor."
    exit 1
}
$Password = (Get-Content $SecretFile -Raw).Trim()

# Intentar con pscp (PuTTY) si existe
$pscp = Get-Command pscp -ErrorAction SilentlyContinue
if ($pscp) {
    Write-Host "Creando carpeta en el servidor..."
    $plink = Get-Command plink -ErrorAction SilentlyContinue
    if ($plink) {
        & plink -ssh -batch -pw $Password "${User}@${Server}" "mkdir -p $RemotePath"
    }
    Write-Host "Subiendo .env.production..."
    & pscp -batch -pw $Password (Join-Path $ProjectRoot "frontend\.env.production") "${User}@${Server}:${RemotePath}/"
    Write-Host "Subiendo server.env.example..."
    & pscp -batch -pw $Password (Join-Path $ProjectRoot "deploy\server.env.example") "${User}@${Server}:${RemotePath}/"
    Write-Host "Listo."
    exit 0
}

# Sin pscp: usar SCP nativo (pedirá contraseña manualmente)
Write-Host "No se encontró pscp (PuTTY). Usando scp nativo; te pedirá la contraseña."
Write-Host "Servidor: ${User}@${Server}:${RemotePath}"
$env:ProjectRoot = $ProjectRoot
scp -o StrictHostKeyChecking=accept-new `
    (Join-Path $ProjectRoot "frontend\.env.production"), `
    (Join-Path $ProjectRoot "deploy\server.env.example") `
    "${User}@${Server}:${RemotePath}/"
