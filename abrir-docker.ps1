# abrir-docker.ps1 - abre o Docker Desktop + OpenShorts sem cair no erro de socket.
#
# POR QUE EXISTE: o Docker Desktop 4.89 no Windows deixa arquivos .sock da sessao
# anterior em AppData\Local\Docker\run e AppData\Local\docker-secrets-engine.
# Na abertura seguinte ele tenta renomear esses .sock e o Windows recusa:
#   "rename ...sailor-ingest.sock ...sock.stale: The file cannot be accessed by the system"
# Com essas pastas tiradas do caminho, ele cria pastas novas e abre normal.
# (Verificado: 10/09 19:07 pasta renomeada -> engine subiu 19:51; 13/09 pasta
#  velha de 10/09 ainda la -> travou.)

$ErrorActionPreference = "Continue"
$la     = $env:LOCALAPPDATA
$docker = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"
$app    = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
$proj   = "C:\claude sites\Free opus clip\openshorts"
$ts     = Get-Date -Format "yyyyMMdd_HHmmss"

function Engine-Ok {
    & $docker version --format "{{.Server.Version}}" 2>$null | Out-Null
    return ($LASTEXITCODE -eq 0)
}

# 0. Ja esta rodando? So garante o OpenShorts no ar.
if (Engine-Ok) {
    Write-Output "Docker ja esta rodando."
    Set-Location $proj
    & $docker compose up -d
    exit 0
}

# 1. OneDrive segurava arquivos do perfil numa das quedas.
Get-Process OneDrive -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

# 2. Garante que nao sobrou processo do Docker de uma sessao morta.
$vivos = Get-Process "Docker Desktop","com.docker.backend" -ErrorAction SilentlyContinue
if ($vivos) {
    Write-Output "Docker travado de sessao anterior - encerrando..."
    $vivos | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 4
}
wsl.exe --shutdown 2>$null
Start-Sleep -Seconds 3

# 3. Tira do caminho as pastas de socket da sessao anterior (o conserto de verdade).
foreach ($p in @((Join-Path $la "Docker\run"), (Join-Path $la "docker-secrets-engine"))) {
    if (Test-Path $p) {
        $novo = (Split-Path $p -Leaf) + "_velho_$ts"
        try {
            Rename-Item -LiteralPath $p -NewName $novo -ErrorAction Stop
            Write-Output "pasta de socket antiga afastada: $p"
        } catch {
            Write-Output "AVISO: nao consegui afastar $p : $($_.Exception.Message)"
        }
    }
}

# 4. Desliga o Docker AI (Secrets Engine / Inference = mais sockets, e a gente nao usa).
#    Grava SEM BOM: o Docker (Go) nao le JSON com BOM e reseta as configs se ler.
$sf = Join-Path $env:APPDATA "Docker\settings-store.json"
if (Test-Path $sf) {
    try {
        $j = Get-Content $sf -Raw | ConvertFrom-Json
        $j | Add-Member -NotePropertyName EnableDockerAI -NotePropertyValue $false -Force
        $j | Add-Member -NotePropertyName InferenceCanUseGPUVariant -NotePropertyValue $false -Force
        $json = $j | ConvertTo-Json -Depth 10
        [System.IO.File]::WriteAllText($sf, $json, (New-Object System.Text.UTF8Encoding $false))
        Write-Output "Docker AI desligado."
    } catch {
        Write-Output "AVISO: nao consegui editar settings ($($_.Exception.Message)) - segue assim mesmo."
    }
}

# 5. Abre e espera o engine (ate 6 min).
Start-Process $app
Write-Output "Abrindo Docker Desktop (pode levar ate 3 min)..."
$ok = $false
for ($i = 0; $i -lt 72; $i++) {
    Start-Sleep -Seconds 5
    if (Engine-Ok) { $ok = $true; break }
}
if (-not $ok) {
    Write-Output ""
    Write-Output "Docker NAO subiu em 6 min. Olhe a tela: se aparecer erro, clique Quit"
    Write-Output "(NUNCA 'Reset to factory defaults') e rode este script de novo."
    exit 1
}
Write-Output "Docker OK."

# 6. Sobe o OpenShorts.
Set-Location $proj
& $docker compose up -d
Start-Sleep -Seconds 15
& $docker compose ps
Write-Output ""
Write-Output "PRONTO. Painel: http://localhost:5175"
