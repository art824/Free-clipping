#!/usr/bin/env python3
"""repostar.py - repoe na fila os clipes de campanha que ja foram ao ar.

Quando o material novo do criador acaba, a campanha continua pagando por view e
a regra 4 permite republicar o mesmo video (no maximo 3 vezes por perfil por
dia; a regra 5, que proibe duas capas iguais no mesmo dia, deixa isso em 1 por
dia na pratica). Entao o estoque volta pro comeco.

    python repostar.py                      -> mostra o que entraria (nao mexe)
    python repostar.py --aplicar            -> copia os clipes de volta pra fila
    python repostar.py --rodada 3           -> terceira volta (padrao: proxima livre)

O master fica em PRONTOS e o titulo/descricao vem do campanha_historico.json,
porque o .json da fila e apagado 24h depois de postar. A copia vai com nome
novo de proposito: o feed usa o ID do arquivo no Drive como <guid> e o Zapier
pula guid repetido - repor o mesmo arquivo nao publicaria nada.

Depois de rodar, use intercalar.py pra misturar com os clipes normais.
"""

import argparse
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "openshorts"))
import organizar as O  # noqa: E402

FILA = O.PUBLICAR_DRIVE["conta1"]
PRONTOS = os.path.join(O.PRONTOS, "conta1")
HISTORICO = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "campanha_historico.json")


def historico(campanha):
    try:
        with open(HISTORICO, encoding="utf-8") as fh:
            return json.load(fh).get(campanha, [])
    except (OSError, ValueError):
        return []


def achar_master(base):
    """O mp4 original em PRONTOS. O nome pode ter mudado (intercalar renomeia),
    entao casa pelo pedaco estavel: nota + slug."""
    alvo = re.sub(r"^\d{4}-\d{2}-\d{2}_\d{4}_", "", base)
    exato = os.path.join(PRONTOS, base + ".mp4")
    if os.path.exists(exato):
        return exato
    for f in os.listdir(PRONTOS):
        if f.endswith(".mp4") and f[:-4].endswith(alvo):
            return os.path.join(PRONTOS, f)
    return None


def ultimo_slot_da_fila():
    ultimo = None
    for nome in os.listdir(FILA):
        if not nome.endswith(".json"):
            continue
        try:
            with open(os.path.join(FILA, nome), encoding="utf-8") as fh:
                q = O.datetime.fromisoformat(json.load(fh)["publicar_em"])
        except (OSError, ValueError, KeyError):
            continue
        q = q.replace(tzinfo=None)
        if ultimo is None or q > ultimo:
            ultimo = q
    return ultimo or O.agora_brasil()


def repostar_do_drive(args):
    """Copia clipe ja postado (ainda na fila do Drive) com nome novo, pronto pro
    intercalar.py encaixar nos slots de campanha. Serve quando o F: esta fora."""
    agora = O.agora_brasil()
    usadas = [int(m.group(1)) for f in os.listdir(FILA)
              for m in [re.search(r"_r(\d+)\.(mp4|json)$", f)] if m]
    rodada = args.rodada or ((max(usadas) + 1) if usadas else 2)
    achados, slot = [], ultimo_slot_da_fila()
    for trecho in args.do_drive:
        candidatos = []
        for nome in sorted(os.listdir(FILA)):
            if not nome.endswith(".json") or re.search(r"_r\d+\.json$", nome):
                continue
            with open(os.path.join(FILA, nome), encoding="utf-8") as fh:
                d = json.load(fh)
            quando = O.datetime.fromisoformat(d["publicar_em"]).replace(tzinfo=None)
            if quando <= agora and trecho.lower() in d.get("titulo", "").lower() \
                    and os.path.exists(os.path.join(FILA, nome[:-5] + ".mp4")):
                candidatos.append((nome[:-5], d))
        if len(candidatos) != 1:
            print(f"  ! '{trecho}': {len(candidatos)} clipe(s) ja postados batem - preciso de exatamente 1")
            continue
        achados.append(candidatos[0])
    print(f"rodada {rodada} - {len(achados)} clipe(s) do Drive\n")
    for base, d in achados:
        print(f"  {d['titulo'][:76]}")
    if not args.aplicar:
        print("\n(nada foi alterado - use --aplicar; depois rode intercalar.py --aplicar)")
        return 0
    for base, d in achados:
        slot = O.proximo_slot(slot)            # provisorio: o intercalar reposiciona
        nota = (re.search(r"_n(\d+)_", base) or [None, "80"])[1]
        alvo = re.sub(r"^\d{4}-\d{2}-\d{2}_\d{4}_n\d+_", "", base)
        novo = f"{slot:%Y-%m-%d_%H%M}_n{int(nota):02d}_{alvo}_r{rodada}"
        shutil.copy2(os.path.join(FILA, base + ".mp4"), os.path.join(FILA, novo + ".mp4"))
        meta = dict(d)
        meta["publicar_em"] = slot.replace(tzinfo=O.BRASIL).isoformat(timespec="seconds")
        meta["arquivo"] = novo + ".mp4"
        with open(os.path.join(FILA, novo + ".json"), "w", encoding="utf-8") as fh:
            json.dump(meta, fh, ensure_ascii=False, indent=1)
    print(f"\n{len(achados)} clipe(s) copiados como rodada {rodada}. Agora: python intercalar.py --aplicar")
    return 0


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--campanha", default="fabio-neto")
    ap.add_argument("--rodada", type=int, default=0, help="0 = descobre sozinho")
    ap.add_argument("--aplicar", action="store_true")
    ap.add_argument("--do-drive", nargs="+", metavar="TRECHO_DO_TITULO",
                    help="repoe clipes ja postados que AINDA estao na fila do Drive "
                         "(escolhidos por trecho do titulo), sem precisar do F:")
    args = ap.parse_args()

    if args.do_drive:
        return repostar_do_drive(args)

    itens = historico(args.campanha)
    if not itens:
        print(f"nada no historico de '{args.campanha}' - marque clipes primeiro "
              f"(marcar_campanha.py --marcar ...)")
        return 0

    rodada = args.rodada
    if not rodada:
        usadas = [int(m.group(1))
                  for f in os.listdir(FILA) + os.listdir(PRONTOS)
                  for m in [re.search(r"_r(\d+)\.(mp4|json)$", f)] if m]
        rodada = (max(usadas) + 1) if usadas else 2

    ja_repostados = {re.sub(r"_r\d+\.(mp4|json)$", "", f)
                     for f in os.listdir(FILA) if re.search(rf"_r{rodada}\.(mp4|json)$", f)}
    ja_repostados = {re.sub(r"^\d{4}-\d{2}-\d{2}_\d{4}_n\d+_", "", b) for b in ja_repostados}

    plano, slot = [], ultimo_slot_da_fila()
    for it in itens:
        alvo_it = re.sub(r"^\d{4}-\d{2}-\d{2}_\d{4}_n\d+_", "", it["base"])
        if alvo_it in ja_repostados:
            print(f"  = ja repostado na rodada {rodada}: {alvo_it[:50]}")
            continue
        master = achar_master(it["base"])
        if not master:
            print(f"  ! master sumiu do PRONTOS: {it['base']}")
            continue
        slot = O.proximo_slot(slot)
        nota = (re.search(r"_n(\d+)_", it["base"]) or [None, "80"])[1]
        alvo = re.sub(r"^\d{4}-\d{2}-\d{2}_\d{4}_n\d+_", "", it["base"])
        base_novo = f"{slot:%Y-%m-%d_%H%M}_n{int(nota):02d}_{alvo}_r{rodada}"
        plano.append((master, base_novo, slot, it))

    print(f"rodada {rodada} - {len(plano)} clipe(s) do historico de '{args.campanha}'\n")
    for _, base_novo, slot, it in plano:
        print(f"{slot:%d/%m %H:%M}  {it['titulo'][:70]}")

    if not args.aplicar:
        print("\n(nada foi alterado - use --aplicar; depois rode intercalar.py)")
        return 0

    for master, base_novo, slot, it in plano:
        if os.path.exists(os.path.join(FILA, base_novo + ".mp4")):
            continue
        shutil.copy2(master, os.path.join(FILA, base_novo + ".mp4"))
        meta = {
            "titulo": it["titulo"][:100],
            "descricao": it.get("descricao", "")[:4900],
            "publicar_em": slot.replace(tzinfo=O.BRASIL).isoformat(timespec="seconds"),
            "arquivo": base_novo + ".mp4",
        }
        with open(os.path.join(FILA, base_novo + ".json"), "w", encoding="utf-8") as fh:
            json.dump(meta, fh, ensure_ascii=False, indent=1)
    print(f"\n{len(plano)} clipe(s) de volta na fila (rodada {rodada}).")
    print("Agora rode: python intercalar.py --aplicar")
    return 0


if __name__ == "__main__":
    sys.exit(main())
