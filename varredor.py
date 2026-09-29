#!/usr/bin/env python3
"""varredor.py - acha podcast novo que esta bombando e joga na fila de corte.

Usa so o RSS publico do YouTube (sem chave, sem API, sem custo). O RSS de canal
ja traz titulo, data e VIEWS dos ultimos 15 videos - e marca Short no proprio link.

    python varredor.py              -> so mostra o ranking, nao mexe em nada
    python varredor.py --add 2      -> mostra e joga os 2 melhores na fila de corte
    python varredor.py --dias 30    -> olha 30 dias pra tras (padrao: 21)

Ranking e por VIEWS POR DIA, nao por view bruta: video de 3 dias com 60k views
esta mais quente que um de 2 anos com 400k.

Canais ficam em varredor_canais.json (nome -> id ou @handle; handle e resolvido
e gravado na primeira vez). Duracao vem da pagina do video, so pros finalistas,
e fica em cache pra nao buscar duas vezes.
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

RAIZ = os.path.dirname(os.path.abspath(__file__))
CANAIS_JSON = os.path.join(RAIZ, "varredor_canais.json")
CACHE_JSON = os.path.join(RAIZ, "varredor_cache.json")
LINKS = r"F:\OpenShorts\ENTRADA\links_conta1.txt"

MIN_MINUTOS = 20      # abaixo disso nao rende 6 clipes
MAX_MINUTOS = 150     # live gigante trava o corte
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")

CANAIS_PADRAO = {
    "Os Socios Podcast": "@ossocios",
    "PrimoCast": "@PrimoCast",
    "Joel Jota": "UCkzDpSF1zTOnOKbkWT8Xwog",
    "Inteligencia Ltda": "UCvmWNQH4c2T3Triih3lftiw",
    "G4 Educacao": "@G4Educacao",
    "Alfredo Soares": "@alfredosoares",
}


def baixar(url, timeout=30):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept-Language": "pt-BR,pt;q=0.9",
        # sem isso o YouTube devolve a tela de consentimento da UE
        "Cookie": "SOCS=CAI; CONSENT=YES+cb",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def carregar(caminho, padrao):
    try:
        with open(caminho, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return dict(padrao)


def salvar(caminho, dados):
    with open(caminho, "w", encoding="utf-8") as fh:
        json.dump(dados, fh, ensure_ascii=False, indent=1)


def resolver_canal(ref):
    """@handle ou /c/nome -> UC.... Ja recebendo um UC..., devolve como veio."""
    if ref.startswith("UC") and len(ref) == 24:
        return ref
    alvo = ref if ref.startswith("http") else f"https://www.youtube.com/{ref.lstrip('/')}"
    html = baixar(alvo)
    for padrao in (r'"externalId":"(UC[\w-]{22})"',
                   r'"channelId":"(UC[\w-]{22})"',
                   r'channel/(UC[\w-]{22})'):
        m = re.search(padrao, html)
        if m:
            return m.group(1)
    return None


NS = {"a": "http://www.w3.org/2005/Atom",
      "m": "http://search.yahoo.com/mrss/",
      "yt": "http://www.youtube.com/xml/schemas/2015"}


def videos_do_canal(channel_id):
    """Ultimos ~15 videos do canal, direto do RSS publico. Traz views."""
    xml = baixar(f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}")
    raiz = ET.fromstring(xml)
    saida = []
    for e in raiz.findall("a:entry", NS):
        link = e.find("a:link", NS).get("href", "")
        if "/shorts/" in link:      # o RSS marca Short no proprio link
            continue
        s = e.find("m:group/m:community/m:statistics", NS)
        views = int(s.get("views") or 0) if s is not None else 0
        pub = datetime.fromisoformat(e.find("a:published", NS).text)
        saida.append({
            "id": e.find("yt:videoId", NS).text,
            "titulo": e.find("a:title", NS).text or "",
            "publicado": pub,
            "views": views,
        })
    return saida


def duracao_segundos(video_id, cache):
    if video_id in cache:
        return cache[video_id]
    try:
        html = baixar(f"https://www.youtube.com/watch?v={video_id}")
        m = re.search(r'"lengthSeconds":"(\d+)"', html)
        seg = int(m.group(1)) if m else 0
    except (urllib.error.URLError, OSError, ValueError):
        seg = 0          # 0 = nao consegui descobrir; nao descarta o video
    cache[video_id] = seg
    return seg


def ja_na_fila():
    """Ids que ja estao no links_conta1.txt, feitos ou nao."""
    try:
        with open(LINKS, encoding="utf-8-sig") as fh:
            texto = fh.read()
    except OSError:
        return set()
    return set(re.findall(r"(?:v=|youtu\.be/|/live/)([\w-]{11})", texto))


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--dias", type=int, default=21, help="janela de busca (padrao 21)")
    ap.add_argument("--add", type=int, default=0, metavar="N",
                    help="joga os N melhores na fila de corte")
    args = ap.parse_args()

    canais = carregar(CANAIS_JSON, CANAIS_PADRAO)
    cache = carregar(CACHE_JSON, {})
    conhecidos = ja_na_fila()
    agora = datetime.now(timezone.utc)

    candidatos, mudou_canais = [], False
    for nome, ref in list(canais.items()):
        cid = resolver_canal(ref) if not (ref.startswith("UC") and len(ref) == 24) else ref
        if not cid:
            print(f"  ! nao achei o canal {nome} ({ref})")
            continue
        if cid != ref:
            canais[nome], mudou_canais = cid, True
        try:
            videos = videos_do_canal(cid)
        except Exception as e:
            print(f"  ! {nome}: {e}")
            continue
        novos = 0
        for v in videos:
            idade = (agora - v["publicado"]).total_seconds() / 86400
            if idade > args.dias or v["id"] in conhecidos:
                continue
            v["canal"] = nome
            v["idade"] = idade
            v["vpd"] = v["views"] / max(idade, 0.5)
            candidatos.append(v)
            novos += 1
        print(f"  {nome}: {len(videos)} videos, {novos} candidato(s)")

    if mudou_canais:
        salvar(CANAIS_JSON, canais)
    if not candidatos:
        print(f"\nNada novo nos ultimos {args.dias} dias.")
        return 0

    candidatos.sort(key=lambda v: v["vpd"], reverse=True)

    # duracao so pros finalistas: 1 pagina por video, nao pro feed inteiro
    aprovados = []
    for v in candidatos[:15]:
        seg = duracao_segundos(v["id"], cache)
        v["min"] = seg / 60
        if seg and not (MIN_MINUTOS <= v["min"] <= MAX_MINUTOS):
            continue
        aprovados.append(v)
    salvar(CACHE_JSON, cache)

    print(f"\n{'views/dia':>10}  {'views':>9}  {'idade':>6}  {'min':>5}  {'id':<11}  canal / titulo")
    for v in aprovados:
        print(f"{v['vpd']:>10,.0f}  {v['views']:>9,}  {v['idade']:>5.1f}d  "
              f"{v['min']:>5.0f}  {v['id']:<11}  {v['canal']} / {v['titulo'][:52]}")

    if args.add:
        escolhidos = aprovados[:args.add]
        if not escolhidos:
            print("\nNada pra adicionar.")
            return 0
        with open(LINKS, "a", encoding="utf-8") as fh:
            for v in escolhidos:
                fh.write(f"https://www.youtube.com/watch?v={v['id']}\n")
        print(f"\n{len(escolhidos)} link(s) na fila de corte:")
        for v in escolhidos:
            print(f"  + {v['canal']} / {v['titulo'][:60]}")
        print("Rode o RODAR AUTO.bat pra cortar.")
    else:
        print("\n(nada foi alterado - use --add N pra jogar os N melhores na fila)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
