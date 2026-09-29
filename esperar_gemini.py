#!/usr/bin/env python3
"""esperar_gemini.py - so corta quando o Gemini estiver respondendo.

O OpenShorts escolhe os clipes com o Gemini. Quando o modelo esta sobrecarregado
(503 UNAVAILABLE) o job morre DEPOIS de ~25 min de transcricao, o auto.py marca o
link como "# falhou" e a fila inteira queima em tentativas inuteis. Este vigia:

  1. testa o Gemini a cada 3 min com uma chamada minuscula;
  2. so quando responde 2 vezes seguidas roda o auto.py;
  3. se algum link falhar no dia, devolve o link pra fila e espera de novo
     (no maximo 4 rodadas, pra nao ficar em loop num video que falha por outro motivo).

    python esperar_gemini.py            -> espera e corta
    python esperar_gemini.py --testar   -> so mostra se o Gemini responde agora
"""

import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from datetime import datetime

RAIZ = os.path.dirname(os.path.abspath(__file__))
MODELO = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")
LINKS = [r"F:\OpenShorts\ENTRADA\links_conta1.txt", r"F:\OpenShorts\ENTRADA\links_conta2.txt"]
INTERVALO = 180
ESPERA_MAXIMA_H = 14
RODADAS = 4


def log(msg):
    print(f"[{datetime.now():%d/%m %H:%M:%S}] {msg}", flush=True)


def gemini_ok():
    try:
        chave = json.load(open(os.path.join(RAIZ, "auto_config.json"), encoding="utf-8"))["gemini_key"]
        corpo = json.dumps({"contents": [{"parts": [{"text": "Responda apenas: ok"}]}]}).encode()
        req = urllib.request.Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/{MODELO}:generateContent?key={chave}",
            data=corpo, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=45) as r:
            return bool(json.load(r)["candidates"][0]["content"]["parts"][0]["text"])
    except Exception as e:
        return str(getattr(e, "code", e))[:40]


def esperar():
    inicio, seguidos = time.time(), 0
    while time.time() - inicio < ESPERA_MAXIMA_H * 3600:
        r = gemini_ok()
        if r is True:
            seguidos += 1
            log(f"Gemini respondeu ({seguidos}/2)")
            if seguidos >= 2:
                return True
            time.sleep(20)
            continue
        seguidos = 0
        log(f"Gemini fora do ar ({r}) - tento de novo em {INTERVALO // 60} min")
        time.sleep(INTERVALO)
    return False


def devolver_falhas():
    """'# falhou dd/mm: url' de hoje volta a ser 'url'. Devolve quantos."""
    hoje = datetime.now().strftime("%d/%m")
    total = 0
    for caminho in LINKS:
        try:
            with open(caminho, encoding="utf-8-sig") as fh:
                linhas = fh.read().splitlines()
        except OSError:
            continue
        novas = []
        for l in linhas:
            m = re.match(rf"^# falhou {re.escape(hoje)}: (https?://\S+)\s*$", l)
            if m:
                novas.append(m.group(1))
                total += 1
            else:
                novas.append(l)
        with open(caminho, "w", encoding="utf-8") as fh:
            fh.write("\n".join(novas) + "\n")
    return total


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if "--testar" in sys.argv:
        print("Gemini", MODELO, "->", "RESPONDE" if gemini_ok() is True else "FORA DO AR")
        return 0
    for rodada in range(1, RODADAS + 1):
        log(f"=== rodada {rodada}/{RODADAS}: esperando o Gemini ===")
        if not esperar():
            log("Gemini nao voltou a tempo. Desisto; rode de novo quando voltar.")
            return 1
        log("Gemini de pe - rodando o auto.py")
        subprocess.run([sys.executable, os.path.join(RAIZ, "auto.py")], cwd=RAIZ)
        voltaram = devolver_falhas()
        if not voltaram:
            log("Fila concluida sem falhas do dia.")
            return 0
        log(f"{voltaram} link(s) falharam hoje e voltaram pra fila")
    log("Rodadas esgotadas.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
