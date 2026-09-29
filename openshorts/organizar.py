#!/usr/bin/env python3
"""Organiza a saida de um job do OpenShorts pra postagem.

Pega so os clipes finais, copia pra pasta da conta com a DATA E HORA DE
POSTAGEM no nome do arquivo, acrescenta legenda/hashtags/titulo no posts.txt
da conta e apaga a pasta do job (intermediarios, fonte, .ass, etc).

TODOS os horarios sao de BRASILIA (publico do canal), nao do relogio do PC.

Contas em PUBLICAR_DRIVE tambem mandam cada clipe + um .json (titulo,
descricao, horario) pra uma pasta do Google Drive pra Desktop. Na nuvem, o
Apps Script libera o clipe no horario e o Zapier sobe no YouTube - com o PC
desligado.

Uso:
    python organizar.py <job_id> --conta conta1
    python organizar.py --conta conta2                    (job mais recente)
    python organizar.py <job_id> --conta conta1 --manter  (nao apaga o job)

Sai em  F:\\OpenShorts\\PRONTOS\\<conta>\\
    2026-09-14_1200_n92_vender-para-franquias.mp4     (12:00 de Brasilia)
    posts.txt

A agenda de cada conta continua de onde parou (.agenda.json), entao varios
videos da mesma conta nunca disputam o mesmo horario nem sobrescrevem arquivo.
"""

import os
import re
import sys
import json
import shutil
import unicodedata
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

OUTPUT = r"F:\OpenShorts\output"
PRONTOS = r"F:\OpenShorts\PRONTOS"

# Contas que postam sozinhas no YouTube (Drive -> Apps Script -> Zapier).
PUBLICAR_DRIVE = {
    "conta1": r"G:\Meu Drive\PensaComoDono\fila",   # Pensa Como Dono (PT) - YouTube + Instagram
    "conta2": r"G:\Meu Drive\CanalIngles\fila",     # canal em ingles (negocios) - YouTube
    "conta3": r"G:\Meu Drive\CanalGTA6\fila",       # canal de GTA 6 (gameplay + minicam)
}

# Horario do PUBLICO. O Windows desta maquina esta em outro fuso (UTC+2), entao
# nada aqui pode usar datetime.now() puro. Brasil nao tem horario de verao desde 2019.
BRASIL = timezone(timedelta(hours=-3))
# EUA (conta2/conta3, publico ingles) tem horario de verao - usa ZoneInfo (com
# tzdata) em vez de offset fixo, senao o horario real muda 1h em parte do ano.
EUA = ZoneInfo("America/New_York")

# Fuso do PUBLICO de cada conta - decide em que relogio a grade de horarios
# roda. conta1 (Pensa Como Dono) E conta3 (GTA 6 Clips) sao as DUAS conteudo
# PT-BR (titulo, publico), usam Brasilia. So conta2 (Money Cut) e ingles/EUA.
# (Corrigido 28/09/2026 - eu tinha assumido GTA6 como canal em ingles so pelo
# nome do canal/memoria antiga, sem checar os titulos reais da fila - que sao
# em portugues. Arthur corrigiu.)
FUSOS = {"conta1": BRASIL, "conta2": EUA, "conta3": BRASIL}


def fuso_da_conta(conta):
    return FUSOS.get(conta, BRASIL)

# 6 posts por dia, horario de Brasilia (decisao do Arthur, 16/set/2026).
#
# 6 e o teto do que a infra gratis aguenta, nao um numero escolhido a esmo:
# cada conta Zapier gratis da 100 tarefas/mes (1 video = 1 tarefa) e o app de
# YouTube dela limita 5 uploads/24h. O feed do Apps Script se divide em duas
# metades estaveis (?conta=a / ?conta=b), uma por conta Zapier, entao
# 6 x 30 = 180 tarefas caem em 90 por conta. 7/dia ja seriam 105 por conta e
# estourariam; pra passar de 6 e preciso uma TERCEIRA conta (e um ?conta=c).
#
# 18:30 e 21:00 vem da grade antiga de 3x, que ja tinha se provado no canal.
HORARIOS_ANTIGA = [(7, 30), (10, 0), (12, 30), (15, 30), (18, 30), (21, 0)]  # 18-23/09, so referencia

# Grade nova, desde 24/09/2026. Medido na grade antiga, 18 a 23/09, mesmas
# condicoes: 12:30/15:30/18:30 somaram 18 clipes com MAXIMO de 12 views (mediana
# 2 a 4); 07:30/10:00/21:00 somaram 18 clipes com mediana 104 a 196. Os 4 clipes
# de campanha postados as 12:30 morreram (8, 5, 3, 2); os das 07:30 viveram 4 de 4.
# Os 3 horarios vencedores ficam e os 3 mortos viram experimentos vizinhos de
# janelas vivas (06:00 pre-deslocamento, 13:00 que estava vivo na grade de 15-17/09,
# 22:30 extensao da noite). Reavaliar com 5 dias de dado (~29/09) e trocar de novo.
HORARIOS_6X = [(6, 0), (7, 30), (10, 0), (13, 0), (21, 0), (22, 30)]

# Grade dos canais em ingles (conta2/conta3), horario dos EUA (America/New_York).
# PROVISORIO - decidido em 28/09/2026 sem dado de engajamento real desses canais
# (o unico teste medido, [[analise-horarios-24-09]], foi so no @pensecomodonos em
# portugues). Sao os horarios "de manual" pra Shorts em ingles: antes do trabalho,
# almoco, saida do trabalho, noite. Reavaliar assim que houver ~5-6 dias de dado
# na mesma grade pra esses dois canais (mesmo metodo usado pra achar a grade BR).
HORARIOS_US = [(7, 0), (8, 30), (12, 0), (17, 30), (19, 30), (21, 30)]

GRADES = {"conta1": HORARIOS_6X, "conta2": HORARIOS_US, "conta3": HORARIOS_6X}

# Slots reservados pros clipes de campanha, em ordem de prioridade (o melhor clipe
# do dia vai pro primeiro). 07:30 foi o unico que se manteve vivo nos ultimos 3 dias
# (554, 126, 401); 10:00 e 21:00 esfriaram depois de 20/09 mas seguem os melhores
# depois dele. So se aplica a conta1 (a unica com campanha).
SLOTS_CAMPANHA = [(7, 30), (10, 0), (21, 0)]

# Folga pro Google Drive terminar de subir os clipes antes do 1o horario.
ANTECEDENCIA = timedelta(hours=2)
LIMITE_TIKTOK = timedelta(days=10)     # TikTok Studio agenda no maximo 10 dias a frente


def horarios_do_dia(dia, conta="conta1"):
    return GRADES.get(conta, HORARIOS_6X)


def agora_conta(conta="conta1"):
    """Hora de parede no fuso do PUBLICO dessa conta, sem tzinfo (a agenda usa esse relogio)."""
    return datetime.now(fuso_da_conta(conta)).replace(tzinfo=None)


def agora_brasil():
    """Mantido por compatibilidade (fila.py, marcar_campanha.py, repostar.py - todos so conta1)."""
    return agora_conta("conta1")


def slug(txt, limite=40):
    txt = unicodedata.normalize("NFKD", str(txt or ""))
    txt = txt.encode("ascii", "ignore").decode()
    txt = re.sub(r"[^a-zA-Z0-9]+", "-", txt).strip("-").lower()
    return (txt[:limite].rstrip("-")) or "clipe"


def job_mais_recente():
    if not os.path.isdir(OUTPUT):
        return None
    dirs = [d for d in os.listdir(OUTPUT)
            if os.path.isdir(os.path.join(OUTPUT, d)) and len(d) > 30]
    if not dirs:
        return None
    return max(dirs, key=lambda d: os.path.getmtime(os.path.join(OUTPUT, d)))


def carregar_metadata(pasta):
    for f in os.listdir(pasta):
        if f.endswith("_metadata.json"):
            try:
                with open(os.path.join(pasta, f), encoding="utf-8") as fh:
                    d = json.load(fh)
                if isinstance(d, list):
                    return d
                return d.get("shorts", [])
            except Exception as e:
                print(f"  ! metadata ilegivel ({e})")
    return []


def melhor_arquivo(pasta, idx):
    """Arquivo final do clipe idx (1-based): coldopen_ > subtitled_ > cru."""
    alvo = f"_clip_{idx}.mp4"
    arquivos = [f for f in os.listdir(pasta) if f.endswith(alvo)]
    for prefixo in ("coldopen_", "subtitled_"):
        for f in arquivos:
            if f.startswith(prefixo):
                return f
    for f in arquivos:
        if not f.startswith(("coldopen_", "subtitled_", "_co_")):
            return f
    return None


def _agenda_path(pasta_conta):
    return os.path.join(pasta_conta, ".agenda.json")


def carregar_ultimo_slot(pasta_conta):
    try:
        with open(_agenda_path(pasta_conta), encoding="utf-8") as fh:
            return datetime.fromisoformat(json.load(fh)["ultimo"])
    except Exception:
        return None


def salvar_ultimo_slot(pasta_conta, slot):
    with open(_agenda_path(pasta_conta), "w", encoding="utf-8") as fh:
        json.dump({"ultimo": slot.isoformat(timespec="minutes"), "fuso": "Brasilia"}, fh)


def proximo_slot(depois_de, conta="conta1"):
    """Primeiro horario da grade (no fuso do publico da conta) depois de `depois_de`
    e >= agora+ANTECEDENCIA."""
    minimo = agora_conta(conta) + ANTECEDENCIA
    dia = max(depois_de or minimo, minimo).date()
    for _ in range(3660):
        for h, m in horarios_do_dia(dia, conta):
            s = datetime(dia.year, dia.month, dia.day, h, m)
            if s >= minimo and (depois_de is None or s > depois_de):
                return s
        dia += timedelta(days=1)
    raise RuntimeError("nao achei horario livre na agenda")


LIMITE_TITULO_YOUTUBE = 100


def carregar_campanha(chave):
    """Le campanhas.json. Chave ausente/arquivo ausente = None (nada muda)."""
    if not chave:
        return None
    caminho = os.path.join(os.path.dirname(os.path.abspath(__file__)), "campanhas.json")
    try:
        with open(caminho, encoding="utf-8") as fh:
            return json.load(fh).get(chave)
    except (OSError, ValueError):
        return None


def titulo_com_marcacoes(titulo, marcacoes, limite=LIMITE_TITULO_YOUTUBE):
    """Cola as marcacoes obrigatorias da campanha no fim do titulo.

    No YouTube a marcacao TEM que ir no titulo (a descricao nao conta), e o
    titulo para em 100 caracteres. As marcacoes sao fixas, entao quem cede e o
    titulo: corta no limite da palavra pra nao terminar no meio de uma.
    """
    titulo = " ".join(str(titulo or "").split())
    marcacoes = " ".join(str(marcacoes or "").split())
    if not marcacoes:
        return titulo[:limite]
    sobra = limite - len(marcacoes) - 1
    if sobra < 20:
        raise ValueError(
            f"marcacoes ocupam {len(marcacoes)} de {limite} caracteres; "
            f"sobram {sobra} pro titulo, pouco demais pra valer a pena")
    if len(titulo) > sobra:
        titulo = titulo[:sobra].rsplit(" ", 1)[0].rstrip(" ,.;:-–—!?")
    return f"{titulo} {marcacoes}".strip()


def _chave_gemini():
    k = os.environ.get("GEMINI_API_KEY")
    if k:
        return k
    cfg = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "auto_config.json")
    try:
        with open(cfg, encoding="utf-8") as fh:
            return json.load(fh).get("gemini_key")
    except (OSError, ValueError):
        return None


def encurtar_com_ia(titulo, limite):
    """Reescreve o titulo dentro do limite mantendo o gancho.

    Cortar na palavra deixa "O segredo por tras dos 3 bilhoes de views da" -
    perde o sujeito e mata o gancho, que e justamente o que gera a view pela
    qual a campanha paga. Devolve None se nao der certo; quem chama cai no corte.
    """
    chave = _chave_gemini()
    if not chave:
        return None
    modelo = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{modelo}:generateContent?key={chave}")
    import urllib.request

    # Pede com folga: pedindo o limite exato ele erra por 1-2 caracteres e o
    # titulo acaba cortado do mesmo jeito. Segunda tentativa aperta mais.
    for alvo in (limite - 4, limite - 12):
        if alvo < 20:
            break
        prompt = (
            f"Reescreva este titulo de YouTube Short em portugues do Brasil com NO MAXIMO "
            f"{alvo} caracteres, mantendo o mesmo gancho e sentido. Pode cortar palavras "
            f"acessorias, nunca o assunto principal. Conte os caracteres antes de responder. "
            f"Responda SO com o titulo, sem aspas, sem explicacao.\n\nTitulo: {titulo}"
        )
        corpo = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 120},
        }).encode()
        try:
            req = urllib.request.Request(url, data=corpo,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.load(r)
            novo = d["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            print(f"    ! nao consegui encurtar com IA ({type(e).__name__}) - vou cortar")
            return None
        novo = " ".join(novo.replace("<", "").replace(">", "").split()).strip('"“”\' ')
        if novo and len(novo) <= limite:
            return novo
        print(f"    IA devolveu {len(novo)} caracteres (limite {limite}) - tentando de novo")
    return None


def ajustar_titulo_para_campanha(titulo, marcacoes, limite=LIMITE_TITULO_YOUTUBE):
    """Encaixa titulo + marcacoes no limite. Tenta reescrever antes de cortar."""
    titulo = " ".join(str(titulo or "").split())
    marcacoes = " ".join(str(marcacoes or "").split())
    if not marcacoes:
        return titulo[:limite]
    sobra = limite - len(marcacoes) - 1
    if len(titulo) > sobra:
        novo = encurtar_com_ia(titulo, sobra)
        if novo:
            print(f"    titulo encurtado: \"{titulo}\" -> \"{novo}\"")
            titulo = novo
    return titulo_com_marcacoes(titulo, marcacoes, limite)


def publicar_no_drive(pasta_drive, origem_mp4, nome, slot, titulo, descricao,
                      campanha=None, conta="conta1"):
    """Copia o clipe + .json pra pasta do Drive. .json por ultimo: o Apps Script
    so libera o clipe quando os dois existem."""
    base = nome[:-4]
    shutil.copy2(origem_mp4, os.path.join(pasta_drive, nome))
    # A API do YouTube recusa titulo/descricao com < ou > (invalidTitle).
    titulo = " ".join(titulo.replace("<", "").replace(">", "").split()) or "Pensa Como Dono"
    descricao = descricao.replace("<", "").replace(">", "")
    cfg = campanha or {}
    titulo = ajustar_titulo_para_campanha(titulo, cfg.get("marcacoes_no_titulo"))
    # O Instagram nao tem titulo: a marcacao dele tem que ir na legenda, e a lista
    # e OUTRA (cada plataforma tem a sua no painel da Clipei). O feed RSS so expoe
    # titulo e descricao, entao a marcacao do IG vai na DESCRICAO - que e o que o
    # Zap do Instagram usa como legenda. No YouTube isso vira hashtag extra na
    # descricao, inofensivo, porque a marcacao que vale la ja esta no titulo.
    ig = " ".join(str(cfg.get("marcacoes_instagram") or "").split())
    if ig:
        descricao = f"{descricao}\n\n{ig}".strip()
    meta = {
        "titulo": titulo[:100],
        "descricao": descricao[:4900],
        "publicar_em": slot.replace(tzinfo=fuso_da_conta(conta)).isoformat(timespec="seconds"),
        "arquivo": nome,
    }
    with open(os.path.join(pasta_drive, base + ".json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=1)


def organizar(job=None, conta="conta1", manter=False, campanha=None):
    """Organiza um job. Retorna dict com ok, copiados, destino, drive, ultimo_slot.

    `campanha` e a chave em campanhas.json. Sem ela nada muda - as marcacoes
    obrigatorias so entram no job que a pediu, porque marcar um clipe do
    PrimoCast com a hashtag do Fabio seria mentira e derruba a campanha.
    """
    cfg = carregar_campanha(campanha)
    if campanha and not cfg:
        print(f"  ! campanha '{campanha}' nao existe em campanhas.json - seguindo sem marcacao")
    elif cfg:
        print(f"  campanha: {campanha} -> titulo levara \"{cfg.get('marcacoes_no_titulo')}\"")
    job = job or job_mais_recente()
    if not job:
        print("Nenhum job encontrado em", OUTPUT)
        return {"ok": False, "copiados": 0, "drive": 0}
    pasta = os.path.join(OUTPUT, job)
    if not os.path.isdir(pasta):
        print("Pasta do job nao existe:", pasta)
        return {"ok": False, "copiados": 0, "drive": 0}

    print(f"Job: {job}  ->  {conta}")
    shorts = carregar_metadata(pasta)
    if shorts:
        ordem = sorted(enumerate(shorts, start=1),
                       key=lambda p: p[1].get("predicted_score", 0) or 0,
                       reverse=True)
    else:
        print("  ! sem metadata - usando ordem dos arquivos")
        n = len([f for f in os.listdir(pasta)
                 if re.search(r"_clip_\d+\.mp4$", f)
                 and not f.startswith(("coldopen_", "subtitled_", "_co_"))])
        ordem = [(i, {}) for i in range(1, n + 1)]

    destino = os.path.join(PRONTOS, conta)
    os.makedirs(destino, exist_ok=True)
    ultimo = carregar_ultimo_slot(destino)

    pasta_drive = PUBLICAR_DRIVE.get(conta)
    if pasta_drive:
        try:
            os.makedirs(pasta_drive, exist_ok=True)
        except OSError as e:
            print(f"  ! Google Drive indisponivel ({e}) - clipes NAO vao pro YouTube automatico")
            pasta_drive = None

    rotulo_fuso = "Brasilia" if conta == "conta1" else "EUA/ET"
    blocos, copiados, no_drive, fora_limite = [], 0, 0, 0
    for idx, meta in ordem:
        src = melhor_arquivo(pasta, idx)
        if not src:
            print(f"  - clipe {idx}: nenhum arquivo final encontrado")
            continue
        slot = proximo_slot(ultimo, conta)
        nota = int(meta.get("predicted_score", 0) or 0)
        titulo = (meta.get("video_title_for_youtube_short")
                  or meta.get("viral_hook_text") or f"clipe {idx}")
        descricao = meta.get("video_description_for_tiktok") or ""
        nome = f"{slot:%Y-%m-%d_%H%M}_n{nota:02d}_{slug(titulo)}.mp4"
        origem = os.path.join(pasta, src)

        shutil.copy2(origem, os.path.join(destino, nome))
        ultimo = slot
        copiados += 1

        extra = ""
        if pasta_drive:
            try:
                publicar_no_drive(pasta_drive, origem, nome, slot, titulo, descricao, cfg, conta)
                no_drive += 1
                extra = "  [YouTube automatico]"
            except OSError as e:
                extra = f"  [FALHOU ir pro Drive: {e}]"

        tipo = ("com frase-isca" if src.startswith("coldopen_")
                else "legendado" if src.startswith("subtitled_")
                else "SEM legenda")
        longe = (slot - agora_conta(conta)) > LIMITE_TIKTOK
        if longe:
            fora_limite += 1
        blocos.append(
            "=" * 62 + "\n"
            f"POSTAR {slot:%d/%m as %H:%M} ({rotulo_fuso})   nota {nota}   [{tipo}]{extra}"
            + ("   (passa de 10 dias pro TikTok Studio)" if longe else "")
            + f"\narquivo : {nome}\n\n"
            f"--- LEGENDA ---\n"
            f"{descricao or '(sem legenda no metadata)'}\n\n"
            f"--- TITULO ---\n"
            f"{titulo}\n")
        print(f"  + {nome}   ({tipo}){extra}")

    if copiados:
        salvar_ultimo_slot(destino, ultimo)
        with open(os.path.join(destino, "posts.txt"), "a", encoding="utf-8") as fh:
            fh.write(f"\n\n######## LOTE de {agora_conta(conta):%d/%m %H:%M} ({rotulo_fuso})"
                     f" - job {job} ########\n\n" + "\n".join(blocos))
        if not manter:
            liberado = 0
            for raiz, _, arquivos in os.walk(pasta):
                for f in arquivos:
                    try:
                        liberado += os.path.getsize(os.path.join(raiz, f))
                    except OSError:
                        pass
            shutil.rmtree(pasta, ignore_errors=True)
            print(f"\nLimpeza: pasta do job apagada ({liberado / 1048576:.0f} MB liberados)")

    if fora_limite and not pasta_drive:
        print(f"\nAVISO: {fora_limite} clipe(s) passam do limite de 10 dias do TikTok Studio"
              " - poste os mais antigos primeiro.")
    if pasta_drive:
        print(f"\nYouTube automatico: {no_drive} clipe(s) enviados pro Google Drive")
    print(f"PRONTO -> {destino}   ({copiados} clipes novos)")
    return {"ok": copiados > 0, "copiados": copiados, "drive": no_drive,
            "destino": destino, "ultimo_slot": ultimo}


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    args = sys.argv[1:]
    manter = "--manter" in args
    conta = "conta1"
    if "--conta" in args:
        i = args.index("--conta")
        if i + 1 < len(args):
            conta = args[i + 1]
    job = None
    for k, a in enumerate(args):
        if a.startswith("--") or (k > 0 and args[k - 1] == "--conta"):
            continue
        job = a
        break
    r = organizar(job, conta, manter)
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
