#!/usr/bin/env python3
"""marcar_campanha.py - poe (ou tira) as marcacoes de campanha nos clipes da fila.

Serve pro caso normal: o clipe ja foi organizado sem campanha e passou na
conferencia manual da regra ("o especialista aparece em >=50% do video"). Clipe
que reprovou fica sem marcacao e segue como conteudo normal do canal - marcar
um clipe onde ele mal aparece derruba a campanha inteira.

    python marcar_campanha.py --ver                     -> lista a fila e o estado
    python marcar_campanha.py --marcar live-commerce ia-do-jeito
    python marcar_campanha.py --desmarcar jogo-foi-zerado
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "openshorts"))
import organizar as O  # noqa: E402

FILA = O.PUBLICAR_DRIVE["conta1"]
PRONTOS = os.path.join(O.PRONTOS, "conta1")
HISTORICO = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "campanha_historico.json")


def registrar(campanha, base, titulo, descricao):
    """Guarda o clipe no historico da campanha pra poder repostar depois.

    O .json da fila e apagado pelo limpar_fila.py 24h depois de postar, e o
    master do mp4 fica no PRONTOS sem titulo nenhum - sem esse registro nao
    haveria como remontar o repost com a marcacao certa.
    """
    try:
        with open(HISTORICO, encoding="utf-8") as fh:
            h = json.load(fh)
    except (OSError, ValueError):
        h = {}
    itens = h.setdefault(campanha, [])
    for it in itens:
        if it["base"] == base:
            it.update(titulo=titulo, descricao=descricao)
            break
    else:
        itens.append({"base": base, "titulo": titulo, "descricao": descricao})
    with open(HISTORICO, "w", encoding="utf-8") as fh:
        json.dump(h, fh, ensure_ascii=False, indent=1)


def esquecer(campanha, base):
    try:
        with open(HISTORICO, encoding="utf-8") as fh:
            h = json.load(fh)
    except (OSError, ValueError):
        return
    h[campanha] = [i for i in h.get(campanha, []) if i["base"] != base]
    with open(HISTORICO, "w", encoding="utf-8") as fh:
        json.dump(h, fh, ensure_ascii=False, indent=1)


def jsons():
    return sorted(f for f in os.listdir(FILA) if f.endswith(".json"))


def marcado(titulo, marcacoes):
    return marcacoes and marcacoes.split()[0].lower() in (titulo or "").lower()


def sem_marcacoes(titulo, marcacoes):
    """Tira as marcacoes do fim do titulo, se estiverem la."""
    for parte in marcacoes.split():
        titulo = titulo.replace(parte, "")
    return " ".join(titulo.split())


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--campanha", default="fabio-neto")
    ap.add_argument("--ver", action="store_true")
    ap.add_argument("--marcar", nargs="*", default=[], metavar="PEDACO_DO_NOME")
    ap.add_argument("--desmarcar", nargs="*", default=[], metavar="PEDACO_DO_NOME")
    ap.add_argument("--sincronizar", action="store_true",
                    help="registra no historico todo clipe da fila que ja esta marcado")
    ap.add_argument("--legendas", action="store_true",
                    help="preenche legenda_instagram em todos os clipes da fila")
    args = ap.parse_args()

    cfg = O.carregar_campanha(args.campanha)
    if not cfg:
        print(f"campanha '{args.campanha}' nao existe em campanhas.json")
        return 1
    marcacoes = cfg["marcacoes_no_titulo"]

    if args.legendas:
        ig = " ".join(str(cfg.get("marcacoes_instagram") or "").split())
        n = 0
        for nome in jsons():
            caminho = os.path.join(FILA, nome)
            with open(caminho, encoding="utf-8") as fh:
                d = json.load(fh)
            # So leva as marcacoes do Instagram o clipe ja marcado como de
            # campanha no titulo. Vai na descricao porque o feed RSS so expoe
            # titulo e descricao, e a descricao e o que vira legenda no IG.
            base = (d.get("descricao", "") or "").split(ig.split()[0])[0].strip() if ig else d.get("descricao", "")
            nova = f"{base}\n\n{ig}".strip() if (ig and marcado(d.get("titulo"), marcacoes)) else base
            if d.get("descricao") == nova[:4900] and "legenda_instagram" not in d:
                continue
            d.pop("legenda_instagram", None)
            d["descricao"] = nova[:4900]
            with open(caminho, "w", encoding="utf-8") as fh:
                json.dump(d, fh, ensure_ascii=False, indent=1)
            n += 1
        print(f"{n} clipe(s) com legenda_instagram preenchida.")
        return 0

    if args.sincronizar:
        n = 0
        for nome in jsons():
            with open(os.path.join(FILA, nome), encoding="utf-8") as fh:
                d = json.load(fh)
            if marcado(d.get("titulo"), marcacoes):
                registrar(args.campanha, nome[:-5], d["titulo"], d.get("descricao", ""))
                print(f"  registrado: {nome[:-5][:56]}")
                n += 1
        print(f"\n{n} clipe(s) no historico de '{args.campanha}'.")
        return 0

    if args.ver or not (args.marcar or args.desmarcar):
        print(f"marcacoes da campanha '{args.campanha}': {marcacoes}\n")
        for nome in jsons():
            with open(os.path.join(FILA, nome), encoding="utf-8") as fh:
                d = json.load(fh)
            flag = "[CAMPANHA]" if marcado(d.get("titulo"), marcacoes) else "[normal]  "
            print(f"{flag} {nome[:-5][:58]}")
        return 0

    mudou = 0
    for nome in jsons():
        caminho = os.path.join(FILA, nome)
        with open(caminho, encoding="utf-8") as fh:
            d = json.load(fh)
        titulo = d.get("titulo", "")
        alvo_marcar = any(p.lower() in nome.lower() for p in args.marcar)
        alvo_tirar = any(p.lower() in nome.lower() for p in args.desmarcar)

        if alvo_marcar and not marcado(titulo, marcacoes):
            novo = O.ajustar_titulo_para_campanha(titulo, marcacoes)
        elif alvo_tirar and marcado(titulo, marcacoes):
            novo = sem_marcacoes(titulo, marcacoes)
        else:
            continue

        d["titulo"] = novo[:100]
        with open(caminho, "w", encoding="utf-8") as fh:
            json.dump(d, fh, ensure_ascii=False, indent=1)
        if alvo_marcar:
            registrar(args.campanha, nome[:-5], d["titulo"], d.get("descricao", ""))
        else:
            esquecer(args.campanha, nome[:-5])
        print(f"  {nome[:-5][:44]}\n    -> {novo}")
        mudou += 1
    print(f"\n{mudou} clipe(s) alterados.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
