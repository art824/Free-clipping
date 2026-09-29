# Plano — operação faceless de cortes (OpenShorts + campanhas de clipagem)

_Escrito 06/09/2026. Baseado no que foi verificado nesta sessão: repo OpenShorts clonado + lido,
Clipei/ViewX/clipmap acessados logado, pesquisa de mercado 2026. É um snapshot — o que estiver
marcado "VERIFICAR" precisa ser conferido ao vivo, 2x, dias diferentes._

---

## 1. Onde estamos

- **OpenShorts** (clipador open source, self-hosted, Docker + Gemini free tier) — build concluído mas
  **encheu o disco** (C: 28 GB → 5 GB) e o daemon do Docker quebrou (socket preso). Precisa: reboot →
  `docker builder prune -f` (recupera ~12 GB) → subir containers → 1 clipe de teste.
- Objetivo do Arthur: renda de **centenas de reais/mês** para começar, operação **faceless**, contas
  **próprias**, **pouco tempo** (tem que ser automatizável), foco **TikTok + YouTube** (Instagram
  cortado — exige servidor sempre ligado).

---

## 2. Premissa corrigida: o que o OpenShorts faz

Não é "só podcast". É **qualquer conteúdo movido a fala**. O motor:
transcrição → Gemini acha o trecho de 15-60s mais clipável → reenquadre 9:16 → legenda palavra-por-palavra → hook.

**BOM para:** podcast, entrevista, talking-head, **debate/reality falado**, video-essay, sermão, aula,
**webinar**, react/comentário, **tutorial com tela compartilhada**, trechos de "just chatting" de streamer.
Modos SCREENCAST (tela sobre apresentador) e INSET (streamer com webcam no canto) são feitos pra isso.

**INÚTIL para:** música, gameplay puro sem comentário, b-roll silencioso, ASMR, dança.

**Extra:** API REST + MCP + CLI + webhooks + recut. Casa com automação.

---

## 3. O nicho: **negócios / dinheiro / empreendedorismo (PT-BR)**

### Por que esse, e não outro

| Critério | Negócios PT-BR | Música | Streamer/gaming | Podcast genérico (Podpah) |
|---|---|---|---|---|
| OpenShorts encaixa | ✅ (e tem **vantagem** no SCREENCAST) | ❌ | parcial (só "just chatting") | ✅ |
| Modelo CPMV disponível | ✅ (cluster "Komp" no Clipei) | ✅ mas app não serve | ❌ (só ranking) | ❌ (ranking) |
| Perene (não expira) | ✅ | ❌ (morre quando o single "esfria") | ✅ | ✅ |
| Saturação | média | alta | alta | **12.646 envios** — morto |
| Audiência com poder de compra (upside afiliado futuro) | ✅ | ❌ | ❌ | médio |
| CPMV | R$ 1,00–1,75 /mil | — | — | — |

### A vantagem técnica concreta

Criador de negócios ensina muito com **tela compartilhada**. O modo SCREENCAST do OpenShorts reenquadra
isso bonito; clipador com ferramenta tosca deixa torto. **Teu corte fica melhor que o do concorrente**
nesse tipo de conteúdo específico.

### Fontes de long-form pra cortar

O próprio criador da campanha (podcast + canal do YouTube dele). Ex. de universo: Alfredo Soares,
Leonardo Marcondes, Davi Braga, G4, Os Sócios/PrimoCast, Joel Jota, episódios de negócios do Flow,
convidados de negócios da Inteligência Ltda. **Segue a campanha que está aberta** e clipa aquele criador.

### Lane secundária

**Debate / reality falado** (tipo "Canal Foco – Mulheres X Anões", R$ 1,00/mil, IG+YT+TikTok).
Mesmo encaixe de ferramenta. Serve pra ter volume quando as campanhas de negócios estão entre reabastecimentos.

### Fora (não perde tempo)

Toda campanha de música (maioria do Clipei), gameplay puro, campanhas de ranking do ViewX/RealOficial,
Podpah, mercado inglês do Whop (por ora — se o PT secar, o próximo passo é **espanhol**, não inglês).

---

## 4. O mercado real de campanhas (verificado nesta sessão)

| Plataforma | Modelo | Conteúdo dominante | Serve? |
|---|---|---|---|
| **Clipei** (HypeX) | **CPMV** (paga por mil views) + Competições + Quantidade | ~70% sertanejo | **Melhor** — única com CPMV |
| ViewX | 100% ranking | streamer/gaming | Fraca (só Podcast 3 Irmãos) |
| RealOficial | 100% ranking | esports + Podpah | Não |
| clipmap.gg | agregador | Whop/inglês domina (~1.369 de 199 abertas) | BR é fatia pequena |

**Campanhas CPMV que casam no Clipei hoje** (VERIFICAR toda semana — giram rápido, budget esgota):

- **Leonardo Marcondes** — Komp — R$ 1,75/mil — negócios/marketing
- **Alfredo Soares – Apóstolos** — Komp — (taxa não mostrada) — empreendedorismo
- **Davi Braga** — Komp — (taxa não mostrada) — marketing
- **Canal Foco – Mulheres X Anões** — HypeX — R$ 1,00/mil — debate falado
- **6 Milionários x 6 Iniciantes** — HypeX — R$ 1,00/mil — **exclusiva Nitro (assinatura paga?)**

**Realidade dura do dinheiro** (pesquisa 2026): CPM efetivo médio pago ~US$ 0,39, ganho vitalício médio
~US$ 305/clipador, distribuição concentrada no topo. RPM orgânico de TikTok/YT Shorts ≈ zero — **o dinheiro
está nas campanhas**, não na monetização de plataforma.

---

## 5. Plano operacional (por fases)

### Fase 0 — recuperar + provar a cadeia (esta semana)

1. Reboot do Windows → recuperar Docker → `docker builder prune -f` → `docker compose up -d` → confirmar 3 containers
2. **1 clipe de teste** end-to-end (YouTube curto → clipe sai). Prova que a ferramenta funciona.
3. No Clipei, abrir 2 campanhas Komp → aba **Regras** → responder (isto trava tudo):
   - **VERIFICAR:** YouTube conta como plataforma? (a única que abri aceitava só IG+TikTok)
   - **VERIFICAR:** mínimo de views pro corte contar? teto por post/dia?
   - **VERIFICAR:** aceita **conta faceless / repost**? ou exige conta "dedicada" com nome do criador?
   - **VERIFICAR:** "Redes Conectadas" — exige conectar a conta real do TikTok/YT pra medir views?
   - **VERIFICAR:** precisa de **Nitro** (assinatura) pras campanhas boas? quanto custa?
   - **VERIFICAR:** saque mínimo no PIX?
   - **Se faceless/repost for proibido → o plano muda** (contas com nome/branding, ainda viável, mas diferente).

### Fase 1 — 1 conta, 1 lane, semi-manual (semanas 1–4)

- **1 conta TikTok + 1 canal YouTube**, marca faceless de negócios/dinheiro
- Escolher a **1–2 melhores campanhas CPMV Komp** abertas
- **Rotina em lote, 2x/semana:**
  1. Baixar 2–3 episódios long-form do criador da campanha
  2. Rodar OpenShorts → 15–45 cortes
  3. **Seleção humana** dos 10–15 melhores (a parte que NÃO automatiza — é o julgamento)
  4. Ajustar hooks
  5. YouTube: rodar o script da API → agenda os cortes nos próximos 3–4 dias (`publishAt`)
  6. TikTok: TikTok Studio → agendar 10 nos próximos 3 dias
  7. Submeter os cortes na campanha
- **Medir:** quais cortes pegam view, quanto o CPMV efetivo paga de verdade, se TikTok/YT sinalizam algo

### Fase 2 — escalar o que funcionou (semanas 5–12)

- Se a Fase 1 mostrar view real + pagamento real: **+2–3 contas** na mesma lane, espalhadas nas campanhas
- Afinar config do OpenShorts (modelo Whisper, layout padrão) pelo que performou
- Hábito de **radar de campanha**: checar Clipei toda semana, pular nas CPMV recém-abertas ("novo envios")
- Só agora considerar: VPS barato rodando a automação do YouTube sem supervisão, ou expansão pro espanhol

### Fase 3 — ponto de decisão (mês 3+)

- Está batendo centenas de reais/mês de forma consistente?
  - **Sim:** escala contas, considera espanhol, considera oferta própria/afiliado em cima das contas
  - **Não:** o combo nicho+ferramenta+mercado não fecha pra operador solo faceless nessa escala.
    Corta a perda — a infra (OpenShorts) continua reusável pra outras coisas.

---

## 6. Stack de automação (concreta)

| Etapa | Ferramenta | Toque humano |
|---|---|---|
| Clipar | OpenShorts, em lote | roda 1 comando, ~5-8 min/vídeo (CPU) |
| Selecionar | **humano** | ~30 min por lote — inevitável |
| YouTube | script Python, YouTube Data API v3, `videos.insert` + `publishAt` | setup único (OAuth); depois ~2 min/lote, YT publica sozinho |
| TikTok | TikTok Studio web (agendador nativo, 10 posts/10 dias, conta Business/Creator) | ~20 min a cada 3 dias |
| Instagram | — | cortado (exige servidor 24/7) |

**Sem VPS, sem Postiz, sem Instagram** (por ora). Notebook e celular podem ficar off na hora dos posts —
YouTube e TikTok publicam pelos servidores deles.

**Conteúdo "não-original"** (corte cru, marca d'água, logo de outra plataforma) → fora do For You do TikTok.
O que te salva também é teu fosso: seleção humana do trecho + hook + reenquadre + legenda (OpenShorts faz).

---

## 7. Infra (o problema do disco)

- Pós-recuperação + prune: C: ~17 GB. Ainda apertado.
- **Opção A:** rebuildar só o backend com **torch CPU-only** (`--index-url .../whl/cpu` no requirements) →
  corta ~5 GB. 1 edição no `requirements.txt` + rebuild do backend.
- **Opção B:** aceitar apertado — pasta `output` do container → **HD externo**, vídeos de origem no HD externo,
  `docker builder prune` religioso depois de cada sessão.
- **Longo prazo (Fase 2+):** OpenShorts num VPS com GPU — também deixaria ~10x mais rápido. Decisão de custo pra depois.

---

## 8. Riscos — o que falsifica este plano

1. **Faceless/repost pode ser proibido pelas campanhas.** Conferir na aba Regras antes de investir. (Fase 0)
2. **Campanha pode exigir conectar a conta real** ("Redes Conectadas") → complica multi-conta.
3. **CPMV "até R$ X" é tier** — clipe julgado fraco pega o piso (R$ 0,30), não o teto (R$ 1,75).
4. **Budget esgota** ("Premiação restante R$ 2.866" numa que abri) — renda é irregular, exige rotação constante de campanha.
5. **Supressão de "conteúdo não-original"** no For You → se acontecer, view (e renda CPMV) despenca, não importa o resto.
6. **Infra frágil** — esta sessão mostrou que o notebook é marginal pro OpenShorts.
7. **Amostra pequena** — 1 snapshot das listas, 1 página de regras completa. Medir ao vivo, 2x, dias diferentes.

## 9. O que medir — a cadeia causal, elo mais barato primeiro

Provar cada elo com dado real **antes** de escalar:

1. OpenShorts produz um corte usável de um podcast de negócios BR real → **1 clipe de teste**
2. Uma campanha Komp do Clipei de fato permite faceless + TikTok/YT + paga CPMV pra conta nova → **ler regras + 1 submissão real**
3. Um corte postado de fato pega view → **postar 10, ver se algum passa de 5k**
4. Essas views de fato viram R$ num valor que paga o tempo → **conferir o pagamento depois de 2 semanas**

**Só depois do elo 4 provado → escalar contas.**

---

## 10. Próximos passos concretos

1. [ ] Arthur: reiniciar o Windows
2. [ ] Claude: recuperar Docker → prune → subir containers → confirmar
3. [ ] Claude: 1 clipe de teste (link YouTube curto de negócios BR)
4. [ ] Arthur + Claude: abrir 2 campanhas Komp no Clipei, ler aba Regras, responder os "VERIFICAR" da Fase 0
5. [ ] Decidir: rebuild CPU-only torch (corta 5 GB) ou seguir com disco apertado
6. [ ] Setup do script YouTube API (OAuth uma vez)
7. [ ] Criar 1 conta TikTok Business + 1 canal YouTube da marca faceless
8. [ ] Primeiro lote real: 2–3 episódios → cortes → agendar → submeter
