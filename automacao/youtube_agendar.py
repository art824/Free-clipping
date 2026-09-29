#!/usr/bin/env python3
"""
youtube_agendar.py — sobe um lote de cortes pro YouTube como PRIVADO com horario
de publicacao. O YouTube publica sozinho na hora marcada, com teu PC desligado.

--------------------------------------------------------------------------------
SETUP (uma vez so):

1. console.cloud.google.com -> cria um projeto
2. "APIs e servicos" -> Ativar -> "YouTube Data API v3"
3. "Credenciais" -> Criar credenciais -> "ID do cliente OAuth" -> tipo "App para
   computador" -> baixa o JSON e salva aqui como  client_secret.json
4. "Tela de consentimento OAuth" -> External -> adiciona teu email em "Usuarios
   de teste"
5. pip install google-auth-oauthlib google-api-python-client

--------------------------------------------------------------------------------
USO:

  python youtube_agendar.py lote.csv

  lote.csv (uma linha por corte):
    arquivo,titulo,descricao,tags,publicar_em
    F:/OpenShorts/output/clipe01.mp4,Titulo do corte,Descricao aqui,tag1;tag2,2026-09-12 18:00
    F:/OpenShorts/output/clipe02.mp4,Outro titulo,Outra descricao,tag1;tag3,2026-09-12 21:00

  - publicar_em: horario LOCAL (America/Sao_Paulo). O script converte pra UTC.
  - primeira execucao abre o navegador pra você logar e autorizar (uma vez).
    depois disso o token fica salvo em  token.json  e nao pergunta mais.
--------------------------------------------------------------------------------
"""
import csv
import sys
import os
from datetime import datetime, timezone, timedelta

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
except ImportError:
    sys.exit("Falta instalar: pip install google-auth-oauthlib google-api-python-client")

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
HERE = os.path.dirname(os.path.abspath(__file__))
CLIENT_SECRET = os.path.join(HERE, "client_secret.json")
TOKEN = os.path.join(HERE, "token.json")
SAO_PAULO = timezone(timedelta(hours=-3))  # sem horario de verao no Brasil desde 2019


def auth():
    creds = None
    if os.path.exists(TOKEN):
        creds = Credentials.from_authorized_user_file(TOKEN, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CLIENT_SECRET):
                sys.exit(f"Falta o arquivo {CLIENT_SECRET} (ver SETUP no topo do script).")
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
    return build("youtube", "v3", credentials=creds)


def parse_quando(texto):
    dt = datetime.strptime(texto.strip(), "%Y-%m-%d %H:%M").replace(tzinfo=SAO_PAULO)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def subir(yt, linha):
    arq = linha["arquivo"].strip()
    if not os.path.exists(arq):
        print(f"  ! nao encontrei: {arq}  -- pulando")
        return
    publish_at = parse_quando(linha["publicar_em"])
    tags = [t.strip() for t in linha.get("tags", "").split(";") if t.strip()]
    body = {
        "snippet": {
            "title": linha["titulo"].strip()[:100],
            "description": linha.get("descricao", "").strip()[:5000],
            "tags": tags,
            "categoryId": "22",  # People & Blogs
        },
        "status": {
            "privacyStatus": "private",
            "publishAt": publish_at,
            "selfDeclaredMadeForKids": False,
        },
    }
    media = MediaFileUpload(arq, chunksize=-1, resumable=True, mimetype="video/*")
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        if status:
            print(f"  {int(status.progress() * 100)}%", end="\r")
    print(f"  OK  https://youtu.be/{resp['id']}  publica {publish_at}")


def main():
    if len(sys.argv) != 2:
        sys.exit("uso: python youtube_agendar.py lote.csv")
    yt = auth()
    with open(sys.argv[1], newline="", encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
    print(f"{len(linhas)} cortes pra agendar\n")
    for i, linha in enumerate(linhas, 1):
        print(f"[{i}/{len(linhas)}] {linha['titulo'][:60]}")
        try:
            subir(yt, linha)
        except Exception as e:
            print(f"  ! erro: {e}")
    print("\nfeito.")


if __name__ == "__main__":
    main()
