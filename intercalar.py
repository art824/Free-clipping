#!/usr/bin/env python3
"""intercalar.py - reagenda a fila do Drive: campanha nos melhores horarios.

Os slots de campanha (organizar.SLOTS_CAMPANHA, hoje 07:30 / 10:00 / 21:00) ficam
reservados pros clipes de campanha, em ordem de prioridade: o de maior nota do dia
vai pro primeiro slot. Os outros slots da grade (organizar.HORARIOS_6X) recebem os
clipes normais, na ordem em que ja estavam. Clipe de campanha e o que carrega a
primeira marcacao da campanha no titulo - nao depende do nome do arquivo.

    python intercalar.py                    -> mostra o plano (nao mexe)
    python intercalar.py --aplicar          -> renomeia e reescreve os .json
    python intercalar.py --por-dia 2        -> no maximo 2 de campanha por dia (padrao 3)

Idempotente: pode rodar de novo quando entrar clipe de campanha novo (por exemplo
depois de marcar_campanha.py) e ele se encaixa nos slots reservados. Nunca mexe em
clipe cuja hora ja passou ou esta a menos de ANTECEDENCIA de distancia.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "openshorts"))
import organizar as O  # noqa: E402

# FILA agora e escolhida em main() via --conta (conta1 por padrao)


def ler_fila(fila):
    itens = []
    for nome in sorted(os.listdir(fila)):
        if not nome.endswith(".json"):
            continue
        caminho = os.path.join(fila, nome)
        try:
            with open(caminho, encoding="utf-8") as fh:
                d = json.load(fh)
            quando = datetime.fromisoformat(d["publicar_em"]).replace(tzinfo=None)
        except (OSError, ValueError, KeyError):
            continue
        m = re.search(r"_n(\d+)_", nome)
        itens.append({
            "base": nome[:-5], "json": caminho,
            "mp4": d.get("arquivo") or nome[:-5] + ".mp4",
            "quando": quando, "nota": int(m.group(1)) if m else 0,
            "titulo": d.get("titulo", ""), "meta": d,
        })
    return itens


def e_de_campanha(item, marcacoes):
    if not marcacoes:
        return False
    return marcacoes.split()[0].lower() in (item["titulo"] or "").lower()


def montar_plano(fila, campanha, normais, corte, por_dia, grade, slots_camp):
    """Devolve [(item, quando)]. Dia a dia: campanha nos slots reservados (por
    prioridade), normais nos demais. Nada se perde: o que nao coube passa pro dia
    seguinte."""
    plano, fila_c, fila_n = [], list(campanha), list(normais)  # 'fila' e so o caminho, usado abaixo
    dia = corte.date()
    limite = (corte + timedelta(days=120)).date()
    while fila_c or fila_n:
        if dia > limite:
            raise RuntimeError("plano passou de 120 dias, algo esta errado")
        livres = [datetime(dia.year, dia.month, dia.day, h, m) for h, m in grade]
        livres = [s for s in livres if s > corte]
        reservados = [datetime(dia.year, dia.month, dia.day, h, m) for h, m in slots_camp]
        reservados = [s for s in reservados if s in livres]
        for s in reservados[:por_dia]:
            if not fila_c:
                break
            plano.append((fila_c.pop(0), s))
            livres.remove(s)
        for s in livres:
            if fila_n:
                plano.append((fila_n.pop(0), s))
            elif fila_c:                      # sobrou slot e nao ha normal: campanha ocupa
                plano.append((fila_c.pop(0), s))
        dia += timedelta(days=1)
    return plano


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--conta", default="conta1", help="conta1 (padrao, com campanha), conta2, conta3...")
    ap.add_argument("--campanha", default="fabio-neto")
    ap.add_argument("--sem-campanha", action="store_true", help="ignora slots de campanha (grade normal, so intercala horarios)")
    ap.add_argument("--forcar", action="store_true", help="remarca tambem clipe com hora ja passada (fila que nunca foi postada)")
    ap.add_argument("--por-dia", type=int, default=3, help="clipes de campanha por dia (padrao 3)")
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()

    fila = O.PUBLICAR_DRIVE.get(args.conta)
    if not fila:
        print(f"conta '{args.conta}' nao existe em organizar.PUBLICAR_DRIVE")
        return 1
    sem_campanha = args.sem_campanha or args.conta != "conta1"
    marcacoes = None
    if not sem_campanha:
        cfg = O.carregar_campanha(args.campanha)
        if not cfg:
            print(f"campanha '{args.campanha}' nao existe em campanhas.json")
            return 1
        marcacoes = cfg.get("marcacoes_no_titulo")

    itens = ler_fila(fila)
    if not itens:
        print("fila vazia")
        return 0
    corte = O.agora_conta(args.conta) + O.ANTECEDENCIA
    moveis = [i for i in itens if i["quando"] > corte or args.forcar]
    # Ordem da campanha: (1) clipes com "prioridade": true no .json (os testes de
    # repost cuja leitura depende de sair cedo), (2) conteudo NOVO, nunca postado,
    # (3) reposts (sufixo _rN). Dentro de cada grupo, a nota decide.
    def _chave(i):
        repost = bool(re.search(r"_r\d+$", i["base"]))
        return (0 if i["meta"].get("prioridade") else 1, 1 if repost else 0, -i["nota"])

    campanha = sorted([i for i in moveis if e_de_campanha(i, marcacoes)], key=_chave)
    normais = sorted([i for i in moveis if not e_de_campanha(i, marcacoes)], key=lambda i: i["quando"])
    print(f"fila: {len(itens)} | congelados: {len(itens) - len(moveis)} | a remarcar: "
          f"{len(campanha)} de campanha + {len(normais)} normais")
    grade = O.horarios_do_dia(None, args.conta)
    print(f"fuso: {O.fuso_da_conta(args.conta)} | grade: "
          f"{', '.join(f'{h:02d}:{m:02d}' for h, m in grade)} | "
          f"slots de campanha: {', '.join(f'{h:02d}:{m:02d}' for h, m in O.SLOTS_CAMPANHA)}")

    slots_camp = [] if sem_campanha else O.SLOTS_CAMPANHA
    plano = montar_plano(fila, campanha, normais, corte, args.por_dia, grade, slots_camp)

    # so mostra/mexe no que muda
    mudancas = [(i, q) for i, q in plano if q != i["quando"]]
    print(f"\n{len(mudancas)} clipe(s) mudam de horario\n")
    print(f"{'novo':<12} {'antes':<12} nota  titulo")
    for item, quando in sorted(plano, key=lambda p: p[1])[:36]:
        marca = "CAMP" if e_de_campanha(item, marcacoes) else "    "
        print(f"{quando:%d/%m %H:%M} {marca} {item['quando']:%d/%m %H:%M}  n{item['nota']:<3} {item['titulo'][:46]}")
    if len(plano) > 36:
        print(f"... +{len(plano) - 36} clipes")

    if not args.aplicar:
        print("\n(nada foi alterado - use --aplicar)")
        return 0

    # duas fases: nenhum destino pode pisar em arquivo que ainda nao foi movido
    novos = {}
    for item, quando in plano:
        novo = (f"{quando:%Y-%m-%d_%H%M}_n{item['nota']:02d}_"
                f"{item['base'].split('_', 3)[-1]}")
        novos[item['base']] = (novo, quando)
    assert len({n for n, _ in novos.values()}) == len(novos), "colisao de nomes no plano"
    tmp = {}
    for item, quando in plano:
        novo, _ = novos[item['base']]
        if novo == item['base']:
            continue
        t = "~mv_" + item['base']
        os.replace(os.path.join(fila, item['mp4']), os.path.join(fila, t + ".mp4"))
        os.replace(item['json'], os.path.join(fila, t + ".json"))
        tmp[item['base']] = t
    for item, quando in plano:
        if item['base'] not in tmp:
            continue
        novo, q = novos[item['base']]
        meta = dict(item['meta'])
        meta['publicar_em'] = q.replace(tzinfo=O.fuso_da_conta(args.conta)).isoformat(timespec="seconds")
        meta['arquivo'] = novo + ".mp4"
        t = tmp[item['base']]
        os.replace(os.path.join(fila, t + ".mp4"), os.path.join(fila, novo + ".mp4"))
        with open(os.path.join(fila, novo + ".json"), "w", encoding="utf-8") as fh:
            json.dump(meta, fh, ensure_ascii=False, indent=1)
        os.remove(os.path.join(fila, t + ".json"))
    print(f"\n{len(tmp)} clipe(s) remarcados.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
