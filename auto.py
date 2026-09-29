#!/usr/bin/env python3
"""auto.py - corta e organiza tudo sozinho.

1. Abra o Docker:   ABRIR DOCKER.bat
2. Coloque o material em F:\\OpenShorts\\ENTRADA\\ :
      conta1\\   e   conta2\\                  <- videos ja baixados (.mp4 .mkv .webm .mov)
      links_conta1.txt  e  links_conta2.txt   <- links do YouTube, um por linha
3. Rode:            RODAR AUTO.bat
Resultado:  F:\\OpenShorts\\PRONTOS\\conta1\\  e  conta2\\
            (cada arquivo ja tem a data e hora de postar no nome + posts.txt)

Processa um video por vez, alternando as contas. O PC nao dorme enquanto roda.
Pode fechar e rodar de novo depois: o que ja foi feito nao repete
(arquivos vao pra feitos\\ ; links ficam marcados "# feito").
"""

import os
import sys
import json
import time
import shutil
import ctypes
import subprocess
from datetime import datetime

RAIZ = os.path.dirname(os.path.abspath(__file__))
PROJETO = os.path.join(RAIZ, "openshorts")
ENTRADA = r"F:\OpenShorts\ENTRADA"
LOG = r"F:\OpenShorts\auto.log"
API = "http://localhost:8000"
CONTAS = ["conta1", "conta2", "conta3"]
# Layout por conta: GTA 6 recebe gameplay com minicam no canto, entao liga o layout de
# webcam (tela de cima, rosto embaixo, mesmo video = sincronizado). Outras: sem mudanca.
LAYOUTS_POR_CONTA = {"conta3": "auto,screencast"}
EXT_VIDEO = {".mp4", ".mkv", ".webm", ".mov", ".m4v"}
TIMEOUT_JOB_HORAS = 5

sys.path.insert(0, PROJETO)
import organizar  # noqa: E402


def log(msg):
    linha = f"[{datetime.now():%d/%m %H:%M:%S}] {msg}"
    print(linha, flush=True)
    try:
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(linha + "\n")
    except OSError:
        pass


def manter_acordado(ligar):
    """Impede o Windows de suspender enquanto roda (suspender mata o job)."""
    try:
        ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
        flags = ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if ligar else 0)
        ctypes.windll.kernel32.SetThreadExecutionState(flags)
    except Exception:
        pass


def chave_gemini():
    k = os.environ.get("GEMINI_API_KEY")
    if k:
        return k
    cfg = os.path.join(RAIZ, "auto_config.json")
    try:
        with open(cfg, encoding="utf-8") as fh:
            return json.load(fh)["gemini_key"]
    except Exception:
        log(f"ERRO: chave do Gemini nao encontrada em {cfg}")
        sys.exit(1)


def curl(args, timeout):
    r = subprocess.run(["curl.exe", "-s", "-m", str(timeout)] + args,
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.stdout or ""


def api_ok():
    return '"ready"' in curl([f"{API}/health/ready"], 10)


def submeter(item, key, conta=None):
    tipo, valor = item
    lay = LAYOUTS_POR_CONTA.get(conta)
    base = ["-X", "POST", f"{API}/api/process", "-H", f"X-Gemini-Key: {key}"]
    if tipo == "url":
        corpo = {"url": valor, "acknowledged": True}
        if lay:
            corpo["layouts"] = lay
        out = curl(base + ["-H", "Content-Type: application/json",
                           "-d", json.dumps(corpo)], 300)
    else:
        extra = ["-F", f"layouts={lay}"] if lay else []
        out = curl(base + ["-F", f"file=@{valor}", "-F", "acknowledged=true"] + extra, 3600)
    try:
        return json.loads(out)["job_id"]
    except Exception:
        log(f"  nao consegui enviar: {out[:200]}")
        return None


def esperar(job):
    inicio = time.time()
    etapa_anterior, ultimo_print = "", 0.0
    while time.time() - inicio < TIMEOUT_JOB_HORAS * 3600:
        try:
            d = json.loads(curl([f"{API}/api/status/{job}"], 20))
        except Exception:
            time.sleep(30)
            continue
        st = d.get("status", "")
        logs = d.get("logs") or []
        if logs:
            ultima = " ".join(str(logs[-1]).split())[:100]
            etapa = ultima[:14]
            if etapa != etapa_anterior or time.time() - ultimo_print > 300:
                log(f"  {st}: {ultima}")
                etapa_anterior, ultimo_print = etapa, time.time()
        if st == "completed":
            return True
        if st in ("failed", "error", "cancelled"):
            log(f"  job falhou: {d.get('error')}")
            return False
        time.sleep(30)
    log("  tempo esgotado esperando o job")
    return False


def montar_fila():
    por_conta = {}
    for c in CONTAS:
        itens = []
        pasta = os.path.join(ENTRADA, c)
        os.makedirs(pasta, exist_ok=True)
        for f in sorted(os.listdir(pasta)):
            p = os.path.join(pasta, f)
            if os.path.isfile(p) and os.path.splitext(f)[1].lower() in EXT_VIDEO:
                itens.append(("arquivo", p))
        links = os.path.join(ENTRADA, f"links_{c}.txt")
        if os.path.exists(links):
            with open(links, encoding="utf-8-sig") as fh:
                for linha in fh:
                    u = linha.strip()
                    if u and not u.startswith("#"):
                        itens.append(("url", u))
        por_conta[c] = itens
    # alterna as contas: se parar no meio, as duas ja receberam material
    fila = []
    maior = max((len(v) for v in por_conta.values()), default=0)
    # ordem das contas dentro de cada rodada: python auto.py conta3 conta2 (a 1a sai na frente)
    ordem = [c for c in sys.argv[1:] if c in CONTAS] + [c for c in CONTAS if c not in sys.argv[1:]]
    for i in range(maior):
        for c in ordem:
            if i < len(por_conta[c]):
                fila.append((c, por_conta[c][i]))
    return fila


def marcar(conta, item, sucesso):
    tipo, valor = item
    if tipo == "arquivo":
        dest = os.path.join(ENTRADA, conta, "feitos" if sucesso else "falhou")
        os.makedirs(dest, exist_ok=True)
        try:
            shutil.move(valor, os.path.join(dest, os.path.basename(valor)))
        except OSError as e:
            log(f"  nao consegui mover {valor}: {e}")
        return
    links = os.path.join(ENTRADA, f"links_{conta}.txt")
    try:
        with open(links, encoding="utf-8-sig") as fh:
            linhas = fh.read().splitlines()
        tag = "# feito" if sucesso else "# falhou"
        novas = [f"{tag} {datetime.now():%d/%m}: {l}" if l.strip() == valor else l
                 for l in linhas]
        with open(links, "w", encoding="utf-8") as fh:
            fh.write("\n".join(novas) + "\n")
    except OSError as e:
        log(f"  nao consegui marcar o link: {e}")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if not os.path.isdir(r"F:\OpenShorts"):
        print("O HD F: nao esta conectado.")
        return 1
    for c in CONTAS:
        os.makedirs(os.path.join(ENTRADA, c), exist_ok=True)
    if not api_ok():
        print("O OpenShorts nao esta rodando. Abra o ABRIR DOCKER.bat primeiro.")
        return 1

    key = chave_gemini()
    fila = montar_fila()
    if not fila:
        print(f"Nada na ENTRADA. Coloque videos em {ENTRADA}\\conta1 ou conta2,")
        print("ou links do YouTube em links_conta1.txt / links_conta2.txt.")
        return 0

    log(f"=== auto.py: {len(fila)} item(ns) na fila ===")
    manter_acordado(True)
    ok = falhas = clipes = 0
    try:
        for n, (conta, item) in enumerate(fila, 1):
            nome = item[1] if item[0] == "url" else os.path.basename(item[1])
            log(f"[{n}/{len(fila)}] {conta}: {nome}")
            if not api_ok():
                log("  OpenShorts caiu. Parando aqui - abra o ABRIR DOCKER.bat e rode de novo.")
                break
            job = submeter(item, key, conta)
            if not job:
                marcar(conta, item, False)
                falhas += 1
                continue
            log(f"  job {job}")
            if esperar(job):
                r = organizar.organizar(job, conta)
                if r.get("ok"):
                    clipes += r["copiados"]
                    ok += 1
                    marcar(conta, item, True)
                    log(f"  OK: {r['copiados']} clipes -> {r['destino']}")
                    continue
                log("  job terminou mas nenhum clipe final foi encontrado")
            marcar(conta, item, False)
            falhas += 1
    finally:
        manter_acordado(False)
    log(f"=== FIM: {ok} video(s) ok, {falhas} falha(s), {clipes} clipes novos ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
