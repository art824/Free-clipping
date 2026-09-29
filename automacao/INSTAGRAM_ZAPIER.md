# Instagram via Zapier - passo a passo

Configuração 100% ao vivo (conta Meta/Instagram, painel do Zapier) - nada
disso dá pra automatizar ou testar desta sessão cloud. Documentado aqui pra
seguir na sessão local.

## O backend já está pronto - não mexa em código

Conferido em `openshorts/organizar.py:308-334` (`publicar_no_drive`): o pipeline
**já** escreve a marcação de Instagram (`campanhas.json` → `marcacoes_instagram`)
na `descricao` do `.json` de cada clipe, que vira a `<description>` do feed RSS
do Apps Script (`Codigo_novo_com_gta6.gs:184`). Ou seja, a legenda pronta pra
Instagram (com `@fabio_neto_ @startseoficial @kompbr #fnetokp ...` quando for
clipe de campanha) já está no feed, esperando um Zap que a leia. Não precisa
tocar em `organizar.py` nem no `.gs` pra ligar o Instagram - só criar o Zap.

## Pré-requisito: conta Instagram Business/Creator ligada a uma Página do Facebook

O app nativo "Instagram" do Zapier (e a Graph API por trás dele) só publica em
contas **Business ou Creator**, e exige que essa conta esteja vinculada a uma
**Página do Facebook** (mesmo que a página não seja usada pra nada). Sem isso o
Zapier nem lista a conta como opção de publicação.

1. No app do Instagram (celular): Configurações → Conta → mude pra conta
   Profissional (Business ou Creator) se ainda não for.
2. Vincule essa conta a uma Página do Facebook: Configurações → Contas
   vinculadas → Facebook (crie uma Página nova, gratuita, se não tiver
   nenhuma - não precisa seguidor nem post nela, só existir).
3. Confirme em business.facebook.com (Meta Business Suite) que a Página e o
   Instagram aparecem vinculados um ao outro.

## Conectar no Zapier

1. No Zapier, Apps conectados → conectar "Facebook Pages" primeiro (login
   Meta, autorizar, escolher a Página do passo anterior).
2. Conectar "Instagram" (o app específico de publicação) - normalmente pede
   pra escolher a mesma Página/conta Business do passo 1.
3. Se o Zapier pedir permissões extras (Instagram content publishing), aceitar
   - sem isso a ação de postar falha silenciosamente ou fica cinza no editor.

## Criar o Zap

Mesma engrenagem que já funciona pro YouTube - só troca a ação final.

**Trigger:** RSS by Zapier → New Item in Feed
- Feed URL: a MESMA URL `/exec` do Apps Script que os Zaps de YouTube usam,
  com `?canal=<chave-do-canal>&conta=todos`
- **Por que `conta=todos` e não `conta=a`/`conta=b`:** `conta=a`/`b` existem
  pra dividir os clipes entre 2 contas Zapier que postam no MESMO destino
  (YouTube), pra nenhuma repetir o que a outra já postou. O Instagram é um
  destino DIFERENTE - o clipe que vai pro YouTube também deve ir pro
  Instagram, não é dividido com ele. `conta=todos` já existe no código
  (`Codigo_novo_com_gta6.gs`, função `pertenceA_`) exatamente pra esse caso:
  devolve todo item da fila, sem aplicar o filtro a/b.
- Intervalo de checagem: 15 min (igual ao YouTube - é o mínimo do plano
  gratuito do Zapier).

**Action:** Instagram → Publish Photo or Video (Reels)
- Conta: a Business/Creator conectada acima
- Media: mapear o campo `Enclosure Url` (ou `Link`) do trigger RSS - é a URL
  de download direto do Drive (`drive.usercontent.google.com/download?id=...`)
- Caption/Legenda: mapear o campo `Description` do trigger RSS - já vem com a
  marcação de campanha embutida quando for clipe de campanha, não precisa
  editar nada
- Tipo de post: Reels (não "Feed"/foto - os clipes são vídeo vertical)

## Antes de ligar de verdade

1. Rode o Zap em modo de teste com 1 item só e confira no Instagram se: (a) o
   vídeo subiu certo (sem corte, sem tela preta), (b) a legenda veio completa
   com a marcação de campanha quando aplicável, (c) subiu como Reels e não
   como post estático.
2. Só depois disso ligar o Zap (publicação automática a cada 15 min).
3. Confirme que esse Zap está numa conta Zapier com "tasks" sobrando - cada
   post consome 1 task, igual ao YouTube. Ver se cabe dentro do plano atual
   ou se precisa de conta nova (mesmo padrão de "split em 2 contas" que já
   existe pro YouTube, se o volume justificar).

## Depois de funcionar

Quando confirmado que o Instagram está postando certo, considerar repetir
pros outros canais (`themoneycut`, `gta6`) - só trocar `?canal=` na URL do
feed de cada Zap novo. Campanha CPMV (Fábio Neto, e Piero Franceschi quando
sair do pendente) só paga em cima do que sai no Instagram/TikTok, então esse
Zap é o que efetivamente libera a monetização por CPMV - prioridade sobre
qualquer ajuste fino de agenda do YouTube.
