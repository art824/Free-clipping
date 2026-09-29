#!/usr/bin/env python3
"""limpar_fila.py - tira do Google Drive o clipe que ja foi postado.

O Drive e o unico lugar apertado da operacao. O F: tem 566 GB livres e guarda
uma copia de tudo em PRONTOS, entao o clipe nunca se perde: sai do Drive,
continua no HD pra repostar depois.

    python limpar_fila.py            -> so mostra o que sairia (nao apaga nada)
    python limpar_fila.py --apagar   -> apaga de verdade
    python limpar_fila.py --horas 24 -> so o que ja passou ha 24h (padrao: 6)

Regra de seguranca: so sai do Drive o clipe que (1) ja passou da hora de postar
ha mais de N horas e (2) tem copia local confirmada no PRONTOS. Qualquer arquivo
sem copia local fica onde esta e aparece no aviso.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

FILA = r"G:\Meu Drive\PensaComoDono\fila"
PRONTOS = r"F:\OpenShorts\PRONTOS"


def copias_locais():
    nomes = set()
    for raiz, _, arquivos in os.walk(PRONTOS):
        for a in arquivos:
            if a.lower().endswith(".mp4"):
                nomes.add(a)
    return nomes


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser()
    # 24h e nao 6h: cada destino novo (YouTube, Instagram) puxa o mesmo arquivo do
    # Drive no seu proprio ritmo. Apagar cedo demais quebra o destino mais lento.
    ap.add_argument("--horas", type=int, default=24,
                    help="margem depois da hora de postar (padrao 24)")
    ap.add_argument("--apagar", action="store_true", help="apaga de verdade")
    args = ap.parse_args()

    if not os.path.isdir(FILA):
        print("O Google Drive (G:) nao esta montado.")
        return 1

    locais = copias_locais()
    corte = datetime.now(timezone.utc) - timedelta(hours=args.horas)
    sai, fica_sem_copia, mb = [], [], 0.0

    for nome in sorted(os.listdir(FILA)):
        if not nome.endswith(".json"):
            continue
        caminho = os.path.join(FILA, nome)
        try:
            with open(caminho, encoding="utf-8") as fh:
                dados = json.load(fh)
            quando = datetime.fromisoformat(dados["publicar_em"])
        except (OSError, ValueError, KeyError):
            continue
        if quando >= corte:
            continue                      # ainda nao postou, ou postou agorinha
        mp4 = dados.get("arquivo") or nome[:-5] + ".mp4"
        if mp4 not in locais:
            fica_sem_copia.append(mp4)
            continue
        alvos = [caminho]
        p_mp4 = os.path.join(FILA, mp4)
        if os.path.exists(p_mp4):
            mb += os.path.getsize(p_mp4) / 1024 / 1024
            alvos.append(p_mp4)
        sai.append((quando, mp4, alvos))

    if fica_sem_copia:
        print(f"{len(fica_sem_copia)} arquivo(s) SEM copia local - nao vou tocar:")
        for m in fica_sem_copia:
            print(f"  ! {m}")
        print()

    if not sai:
        print(f"Nada pra limpar (nada postado ha mais de {args.horas}h).")
        return 0

    print(f"{len(sai)} clipe(s) postados ha mais de {args.horas}h, {mb:,.0f} MB:")
    for quando, mp4, _ in sai:
        print(f"  - {quando:%d/%m %H:%M}  {mp4[:64]}")

    if not args.apagar:
        print(f"\n(nada foi apagado - use --apagar pra liberar os {mb:,.0f} MB)")
        return 0

    n = 0
    for _, mp4, alvos in sai:
        for a in alvos:
            try:
                os.remove(a)
            except OSError as e:
                print(f"  nao consegui apagar {os.path.basename(a)}: {e}")
                break
        else:
            n += 1
    print(f"\n{n} clipe(s) fora do Drive, {mb:,.0f} MB livres. Copia continua em {PRONTOS}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
