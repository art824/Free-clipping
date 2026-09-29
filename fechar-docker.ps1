# fechar-docker.ps1 - desliga OpenShorts + Docker na ordem certa, pra poder ejetar o F:.
#
# Ordem importa: primeiro para os containers (soltam as pastas do F:), depois a VM
# do WSL (para de escrever no disco do Docker), so entao fecha o Docker Desktop.
# Os .sock que sobrarem nao importam: o abrir-docker.ps1 limpa na proxima abertura.

$docker = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"
$proj   = "C:\claude sites\Free opus clip\openshorts"

# Tem clipe sendo processado agora? (o job atualiza o .resume.json a cada 10s)
$emAndamento = Get-ChildItem "F:\OpenShorts\output\*\.resume.json" -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.LastWriteTime -gt (Get-Date).AddSeconds(-90) }
if ($emAndamento) {
    Write-Output "ATENCAO: tem $($emAndamento.Count) video sendo processado AGORA."
    Write-Output "Fechar interrompe ele (ele retoma sozinho na proxima vez que abrir)."
    $r = Read-Host "Fechar mesmo assim? (s/n)"
    if ($r -notmatch '^[sS]') { Write-Output "Cancelado."; exit 0 }
}

Write-Output "1/3 Parando OpenShorts (solta o F:)..."
Set-Location $proj
& $docker compose down 2>&1 | Out-Null

Write-Output "2/3 Desligando a VM do Docker..."
wsl.exe --shutdown 2>$null
Start-Sleep -Seconds 4

Write-Output "3/3 Fechando o Docker Desktop..."
Get-Process "Docker Desktop","com.docker.backend","com.docker.build" -ErrorAction SilentlyContinue |
    Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3

$sobrou = Get-Process "Docker Desktop","com.docker.backend" -ErrorAction SilentlyContinue
if ($sobrou) {
    Write-Output "AVISO: o Docker ainda nao fechou. Clique com o direito na baleia (bandeja) -> Quit."
} else {
    Write-Output ""
    Write-Output "PRONTO. Pode ejetar o F: com seguranca."
}
