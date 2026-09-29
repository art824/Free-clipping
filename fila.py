#!/usr/bin/env python3
"""fila.py - mostra as filas do Drive (so o que ainda vai ao ar) marcando as de campanha.
    python fila.py            -> Pense como donos + Money Cut
    python fila.py --tudo     -> inclui os que ja sairam
"""
import json, os, sys
from datetime import datetime
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "openshorts"))
import organizar as O

def main():
    try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
    tudo = "--tudo" in sys.argv
    agora = O.agora_brasil().replace(tzinfo=None)
    camp = (O.carregar_campanha("fabio-neto") or {}).get("marcacoes_no_titulo", "@startseoficial").split()[0].lower()
    for nome, pasta in (("PENSE COMO DONOS", O.PUBLICAR_DRIVE["conta1"]), ("THE MONEY CUT", O.PUBLICAR_DRIVE["conta2"])):
        itens = []
        for f in sorted(os.listdir(pasta)):
            if f.endswith(".json"):
                d = json.load(open(os.path.join(pasta, f), encoding="utf-8"))
                q = datetime.fromisoformat(d["publicar_em"]).replace(tzinfo=None)
                itens.append((q, d.get("titulo", ""), f))
        fut = [i for i in itens if i[0] > agora]
        camp_n = sum(camp in t.lower() for _, t, _ in fut)
        print(f"\n=== {nome}: {len(fut)} na fila" + (f" ({camp_n} de CAMPANHA)" if camp_n else "") + f" | ate {fut[-1][0]:%d/%m %H:%M}" if fut else f"\n=== {nome}: fila vazia")
        for q, t, f in (itens if tudo else fut):
            tag = "[CAMPANHA]" if camp in t.lower() else "          "
            rp = " repost" if "_r" in f[:-5].rsplit("_", 1)[-1:][0:1] and f[:-5].split("_")[-1].startswith("r") and f[:-5].split("_")[-1][1:].isdigit() else ""
            print(f"{q:%d/%m %H:%M} {tag} {t[:60]}{rp}")

main()
