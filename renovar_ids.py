#!/usr/bin/env python3
"""renovar_ids.py - da um ID NOVO do Drive pra cada clipe de uma fila.

Por que existe: o Zapier (RSS by Zapier) nunca repete um <guid>, e o nosso guid
e o ID do arquivo no Drive (video.getId() no Apps Script). Renomear o arquivo
(o que intercalar.py faz pra mudar o horario) NAO muda esse ID - o Google Drive
for Desktop trata renome como o MESMO arquivo. Resultado: se o Zap foi ligado
DEPOIS que os clipes ja existiam na pasta, o primeiro poll do Zapier marcou
todos como "ja vistos" pelo ID, e nenhum reagendamento de horario desgruda isso.

A unica forma de o Zapier considerar o clipe "novo" e ele nascer como um
ARQUIVO NOVO de verdade (bytes copiados pra um nome novo -> Drive sobe um ID
novo -> guid novo). E o mesmo truque que repostar.py ja usa pros reposts da
campanha.

    python renovar_ids.py --conta conta3           -> mostra o que faria
    python renovar_ids.py --conta conta3 --aplicar -> copia+apaga de verdade

So mexe nos itens com PUBLICAR_EM AINDA NO FUTURO (nao mexe no que ja passou
da hora - isso o Apps Script ja escondeu do feed, entao ja era).
"""
import argparse
import json
import os
import shutil
import sys
import uuid
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "openshorts"))
import organizar as O  # noqa: E402


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--conta", default="conta3")
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()

    fila = O.PUBLICAR_DRIVE.get(args.conta)
    if not fila:
        print(f"conta '{args.conta}' nao existe em organizar.PUBLICAR_DRIVE")
        return 1

    agora = O.agora_brasil().replace(tzinfo=None)
    itens = []
    for nome in sorted(os.listdir(fila)):
        if not nome.endswith(".json"):
            continue
        base = nome[:-5]
        caminho = os.path.join(fila, nome)
        try:
            meta = json.load(open(caminho, encoding="utf-8"))
            quando = datetime.fromisoformat(meta["publicar_em"]).replace(tzinfo=None)
        except (OSError, ValueError, KeyError):
            continue
        if quando <= agora:
            continue  # ja escondido do feed - nao precisa de ID novo
        mp4 = os.path.join(fila, meta.get("arquivo") or base + ".mp4")
        if not os.path.exists(mp4):
            print(f"  ! sem .mp4 pra {base}, pulando")
            continue
        itens.append((base, caminho, mp4, meta))

    print(f"{len(itens)} clipe(s) futuro(s) em '{args.conta}' vao virar arquivo novo no Drive:")
    for base, _, _, meta in itens:
        print(f"  {meta['publicar_em']}  {meta.get('titulo', base)[:60]}")

    if not args.aplicar:
        print("\n(nada foi alterado - use --aplicar)")
        return 0

    for base, caminho_json, mp4, meta in itens:
        novo_base = base + "_v" + uuid.uuid4().hex[:6]
        novo_mp4 = os.path.join(fila, novo_base + ".mp4")
        novo_json = os.path.join(fila, novo_base + ".json")
        print(f"  copiando {os.path.basename(mp4)} -> {os.path.basename(novo_mp4)} ...", flush=True)
        shutil.copy2(mp4, novo_mp4)
        meta["arquivo"] = novo_base + ".mp4"
        with open(novo_json, "w", encoding="utf-8") as fh:
            json.dump(meta, fh, ensure_ascii=False, indent=1)
        os.remove(mp4)
        os.remove(caminho_json)
        print(f"    ok: {novo_base}")
    print(f"\n{len(itens)} clipe(s) renovados - vao aparecer como item NOVO no proximo poll do Zapier.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
