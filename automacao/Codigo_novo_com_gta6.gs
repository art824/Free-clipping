/**
 * Fila de postagem do YouTube (roda na nuvem do Google, gratis).
 * Serve VARIOS canais - cada um com sua propria pasta no Drive.
 *
 * COMO FUNCIONA
 *  - O PC copia cada clipe (.mp4) + um .json (titulo, descricao, horario) pra
 *    uma pasta do "Meu Drive" - uma pasta por canal. O Google Drive pra
 *    Desktop sobe sozinho.
 *  - Este script publica um feed RSS que so mostra os clipes cujo horario JA
 *    chegou. O parametro canal=SUACHAVE escolhe a pasta (padrao: "pensecomodonos").
 *  - O Zapier (gratis) le o feed a cada 15 min e sobe cada item novo no
 *    YouTube. Como o app de YouTube do Zapier e verificado, o video sai
 *    publico. (Upload direto daqui do Apps Script ficaria travado privado.)
 *  - limpar() manda pra lixeira os clipes que ja passaram do horario ha 2+
 *    dias, nas pastas de TODOS os canais.
 *  - conta=a / conta=b na URL divide o feed de UM canal em 2 metades estaveis
 *    (pelo ID do arquivo no Drive), pra rodar 2 Zaps (2 contas Zapier) sem
 *    nenhum repetir o clipe que o outro ja postou. Sem esse parametro, devolve
 *    tudo (usado pelo testarFeed() e por quem so tem 1 Zap nesse canal).
 *
 * COMPATIBILIDADE: nenhum Zap existente manda ?canal=..., entao todos
 * continuam caindo no canal padrao (Pensa Como Dono), exatamente como antes
 * desta mudanca. So um Zap novo, apontado com ?canal=SUACHAVE, usa uma pasta
 * nova.
 *
 * ADICIONAR UM CANAL NOVO (uma vez por canal) - UM LUGAR SO: o objeto CANAIS
 * abaixo. Acrescente uma chave nova com pasta + ytId (+ titulo, + marcaCampanha
 * se esse canal tiver campanha). Nao precisa mexer em mais nada no backend.
 *  1. Acrescente a entrada em CANAIS.
 *  2. Implantar > Gerenciar implantacoes > lapis > Nova versao > Implantar.
 *  3. No Zapier, use a URL /exec de sempre + "?canal=SUACHAVE" (+ "&conta=a"
 *     ou "&conta=b" se for dividir entre 2 contas Zapier).
 */

var CANAL_PADRAO = 'pensecomodonos';

// Fonte unica de verdade por canal. Pasta = caminho dentro do "Meu Drive".
// ytId = o "UC..." longo do canal (nao o @handle - achar vendo o codigo-fonte
// do canal, campo "externalId"). marcaCampanha = so nos canais que tem
// campanha ativa: primeira palavra da marcacao no titulo (ver campanhas.json
// no projeto) - e assim que intercalar.py tambem decide "isso e campanha".
var CANAIS = {
  pensecomodonos: {
    pasta: 'PensaComoDono/fila',
    ytId: 'UCvYxN31LnE2sAzf9Pp-SLOA',
    titulo: 'Pensa Como Dono - fila',
    marcaCampanha: '@startseoficial'
  },
  themoneycut: {
    pasta: 'CanalIngles/fila',
    ytId: 'UCE7Lgifm_CmP1V-a-54mJxg',
    titulo: 'The Money Cut - queue'
  },
  gta6: {
    pasta: 'CanalGTA6/fila',
    ytId: 'UCPY-W0lxe6izchSTMxOq-tg',
    titulo: 'GTA 6 - queue'
  }
  // proximo canal: so uma entrada aqui, ex.:
  // outronome: { pasta: 'PastaDoDrive/fila', ytId: 'UC...', titulo: 'Nome - fila' }
};

var DIAS_ATE_LIMPAR = 2;
var MAX_ITENS = 25;

function doGet(e) {
  var p = (e && e.parameter) || {};
  if (p.dados) {
    // Painel (dashboard): JSON com fila + estatisticas de todos os canais.
    // Nunca usado pelo Zapier - so pela pagina do painel.
    var json = JSON.stringify(dadosPainel_());
    return ContentService.createTextOutput(json).setMimeType(ContentService.MimeType.JSON);
  }
  var canal = p.canal ? String(p.canal).toLowerCase() : CANAL_PADRAO;
  var conta = p.conta ? String(p.conta).toLowerCase() : null;
  var itens = itensVencidos_(new Date(), conta, canal);
  var xml = montarFeed(itens, ScriptApp.getService().getUrl(), canal);
  return ContentService.createTextOutput(xml).setMimeType(ContentService.MimeType.RSS);
}

function pasta_(canal) {
  var cfg = CANAIS[canal];
  if (!cfg) return null;
  var atual = DriveApp.getRootFolder();
  var partes = cfg.pasta.split('/');
  for (var i = 0; i < partes.length; i++) {
    var it = atual.getFoldersByName(partes[i]);
    if (!it.hasNext()) return null;
    atual = it.next();
  }
  return atual;
}

function lerMeta_(arquivoJson) {
  try {
    return JSON.parse(arquivoJson.getBlob().getDataAsString('UTF-8'));
  } catch (err) {
    return null;
  }
}

/**
 * Separa os clipes em 2 grupos estaveis (a/b) pelo ID do arquivo no Drive.
 * conta=null (sem filtro) devolve todos - compatibilidade com 1 Zap so.
 */
function pertenceA_(id, conta) {
  if (conta === 'todos') return true;
  if (!conta) conta = 'a';  // Zap A antigo nao manda parametro: fica com a metade 'a'
  var soma = 0;
  for (var i = 0; i < id.length; i++) soma += id.charCodeAt(i);
  var grupo = (soma % 2 === 0) ? 'a' : 'b';
  return grupo === conta;
}

function itensVencidos_(agora, conta, canal) {
  var pasta = pasta_(canal || CANAL_PADRAO);
  if (!pasta) return [];
  var jsons = {};
  var videos = {};
  var arquivos = pasta.getFiles();
  while (arquivos.hasNext()) {
    var f = arquivos.next();
    var nome = f.getName();
    if (/\.json$/i.test(nome)) jsons[nome.replace(/\.json$/i, '')] = f;
    else if (/\.mp4$/i.test(nome)) videos[nome.replace(/\.mp4$/i, '')] = f;
  }
  var itens = [];
  for (var base in videos) {
    if (!jsons[base]) continue;              // .json ainda nao subiu
    var meta = lerMeta_(jsons[base]);
    if (!meta) continue;
    var quando = new Date(meta.publicar_em);
    if (isNaN(quando.getTime()) || quando > agora) continue;   // ainda nao e a hora
    var video = videos[base];
    if (!pertenceA_(video.getId(), conta)) continue;
    if (video.getSharingAccess() !== DriveApp.Access.ANYONE_WITH_LINK) {
      // o Zapier precisa conseguir baixar o arquivo pelo link
      video.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW);
    }
    itens.push({
      id: video.getId(),
      titulo: meta.titulo || base,
      descricao: meta.descricao || '',
      quando: quando,
      tamanho: video.getSize(),
      url: 'https://drive.usercontent.google.com/download?id=' + video.getId() +
           '&export=download&confirm=t'
    });
  }
  itens.sort(function (a, b) { return b.quando - a.quando; });
  return itens.slice(0, MAX_ITENS);
}

/**
 * XML 1.0 so aceita tab (9), quebra de linha (10), retorno (13) e codigos >= 32.
 * Qualquer outro caractere de controle num titulo quebraria o feed INTEIRO.
 * Feito por codigo numerico de proposito: nenhum caractere especial no fonte.
 */
function semControle_(s) {
  var out = '';
  for (var i = 0; i < s.length; i++) {
    var c = s.charCodeAt(i);
    if (c === 9 || c === 10 || c === 13 || (c >= 32 && c !== 65534 && c !== 65535)) {
      out += s.charAt(i);
    }
  }
  return out;
}

function esc_(s) {
  return semControle_(String(s))
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&apos;');
}

/** Monta o XML do feed. Funcao pura (testavel fora do Google). */
function montarFeed(itens, urlBase, canal) {
  var cfg = CANAIS[canal];
  var p = [];
  p.push('<?xml version="1.0" encoding="UTF-8"?>');
  p.push('<rss version="2.0"><channel>');
  p.push('<title>' + esc_((cfg && cfg.titulo) || 'fila') + '</title>');
  p.push('<link>' + esc_(urlBase || 'https://script.google.com') + '</link>');
  p.push('<description>Clipes liberados pra postar</description>');
  for (var i = 0; i < itens.length; i++) {
    var it = itens[i];
    p.push('<item>' +
      '<title>' + esc_(it.titulo) + '</title>' +
      '<description>' + esc_(it.descricao) + '</description>' +
      '<link>' + esc_(it.url) + '</link>' +
      '<guid isPermaLink="false">' + esc_(it.id) + '</guid>' +
      '<pubDate>' + it.quando.toUTCString() + '</pubDate>' +
      '<enclosure url="' + esc_(it.url) + '" length="' + (it.tamanho || 0) + '" type="video/mp4"/>' +
      '</item>');
  }
  p.push('</channel></rss>');
  return p.join('\n');
}

/** Lixeira pros clipes cujo horario passou ha mais de DIAS_ATE_LIMPAR dias, em TODOS os canais. */
function limpar() {
  var limite = new Date(Date.now() - DIAS_ATE_LIMPAR * 24 * 3600 * 1000);
  var totalRemovidos = 0;
  Object.keys(CANAIS).forEach(function (canal) {
    var pasta = pasta_(canal);
    if (!pasta) return;
    var jsons = [];
    var arquivos = pasta.getFiles();
    while (arquivos.hasNext()) {
      var f = arquivos.next();
      if (/\.json$/i.test(f.getName())) jsons.push(f);
    }
    jsons.forEach(function (j) {
      var meta = lerMeta_(j);
      if (!meta) return;
      var quando = new Date(meta.publicar_em);
      if (isNaN(quando.getTime()) || quando > limite) return;
      var base = j.getName().replace(/\.json$/i, '');
      var vids = pasta.getFilesByName(base + '.mp4');
      while (vids.hasNext()) { vids.next().setTrashed(true); }
      j.setTrashed(true);
      totalRemovidos++;
    });
  });
  Logger.log(totalRemovidos + ' clipe(s) antigos mandados pra lixeira (todos os canais)');
}

/** Rode UMA vez: agenda o limpar() todo dia as 4h. */
function instalarLimpeza() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'limpar') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('limpar').timeBased().everyDays(1).atHour(4).create();
  Logger.log('Limpeza diaria instalada.');
}

/** Rode no editor pra ver o feed no log (Executar > testarFeed > Registro de execucao). */
function testarFeed() {
  Object.keys(CANAIS).forEach(function (canal) {
    var itens = itensVencidos_(new Date(), 'todos', canal);
    Logger.log('[' + canal + '] ' + itens.length + ' clipe(s) liberado(s) no feed agora');
    Logger.log(montarFeed(itens, 'teste', canal));
  });
}

// ---------------------------------------------------------------------------
// PAINEL (dashboard): tudo daqui pra baixo so serve pra pagina de overview.
// Nao mexe em nada que o Zapier usa.
// ---------------------------------------------------------------------------

/** Le a pasta inteira do canal (fila completa, passado e futuro), sem
 * filtrar por horario nem por conta a/b - e a visao "o que existe hoje". */
function listarFilaCompleta_(canal) {
  var cfg = CANAIS[canal];
  var pasta = pasta_(canal);
  if (!pasta) return [];
  var jsons = {}, videos = {};
  var arquivos = pasta.getFiles();
  while (arquivos.hasNext()) {
    var f = arquivos.next();
    var nome = f.getName();
    if (/\.json$/i.test(nome)) jsons[nome.replace(/\.json$/i, '')] = f;
    else if (/\.mp4$/i.test(nome)) videos[nome.replace(/\.mp4$/i, '')] = f;
  }
  var marca = cfg && cfg.marcaCampanha ? cfg.marcaCampanha.toLowerCase() : null;
  var itens = [];
  for (var base in videos) {
    if (!jsons[base]) continue;
    var meta = lerMeta_(jsons[base]);
    if (!meta) continue;
    var quando = new Date(meta.publicar_em);
    if (isNaN(quando.getTime())) continue;
    itens.push({
      titulo: meta.titulo || base,
      quando: quando.toISOString(),
      campanha: marca ? (meta.titulo || '').toLowerCase().indexOf(marca) !== -1 : false
    });
  }
  itens.sort(function (a, b) { return new Date(a.quando) - new Date(b.quando); });
  return itens;
}

/** Estatisticas publicas do canal (funciona com QUALQUER canal, nao so os
 * seus - e o endpoint publico Channels.list). */
function statsCanal_(channelId) {
  var r = YouTube.Channels.list('snippet,statistics,contentDetails', { id: channelId });
  if (!r.items || !r.items.length) throw new Error('canal nao encontrado: ' + channelId);
  var c = r.items[0];
  return {
    nome: c.snippet.title,
    inscritos: Number(c.statistics.subscriberCount || 0),
    views_totais: Number(c.statistics.viewCount || 0),
    total_videos: Number(c.statistics.videoCount || 0),
    uploads_playlist: c.contentDetails.relatedPlaylists.uploads
  };
}

/** Videos publicados nas ultimas N horas - pra comparar "devia ter postado"
 * (fila) contra "postou de verdade" (YouTube). */
function postadosRecentes_(uploadsPlaylistId, horas) {
  var limite = new Date(Date.now() - horas * 3600 * 1000);
  var r = YouTube.PlaylistItems.list('snippet,contentDetails', {
    playlistId: uploadsPlaylistId, maxResults: 25
  });
  var out = [];
  (r.items || []).forEach(function (it) {
    var pub = new Date(it.contentDetails.videoPublishedAt || it.snippet.publishedAt);
    if (pub > limite) {
      out.push({
        titulo: it.snippet.title,
        publicado_em: pub.toISOString(),
        video_id: it.contentDetails.videoId
      });
    }
  });
  out.sort(function (a, b) { return new Date(b.publicado_em) - new Date(a.publicado_em); });
  return out;
}

/** Todos os videos do canal (nao so os recentes) com o numero de views de
 * cada um - pra media, mediana e destaques. paginacao de 50 em 50 (limite
 * da API); ate MAX_VIDEOS_STATS pra nao estourar tempo/cota num canal grande. */
var MAX_VIDEOS_STATS = 200;

function listarVideosCanal_(uploadsPlaylistId) {
  var ids = [];
  var pageToken = null;
  do {
    var r = YouTube.PlaylistItems.list('contentDetails', {
      playlistId: uploadsPlaylistId, maxResults: 50, pageToken: pageToken
    });
    (r.items || []).forEach(function (it) { ids.push(it.contentDetails.videoId); });
    pageToken = r.nextPageToken;
  } while (pageToken && ids.length < MAX_VIDEOS_STATS);

  var videos = [];
  for (var i = 0; i < ids.length; i += 50) {
    var lote = ids.slice(i, i + 50);
    var r2 = YouTube.Videos.list('snippet,statistics', { id: lote.join(',') });
    (r2.items || []).forEach(function (v) {
      videos.push({
        video_id: v.id,
        titulo: v.snippet.title,
        publicado_em: v.snippet.publishedAt,
        views: Number((v.statistics && v.statistics.viewCount) || 0)
      });
    });
  }
  return videos;
}

/** Percentil por interpolacao linear (metodo padrao) sobre uma lista JA
 * ordenada. p entre 0 e 1. */
function percentil_(ordenadaAsc, p) {
  if (!ordenadaAsc.length) return 0;
  var idx = p * (ordenadaAsc.length - 1);
  var lo = Math.floor(idx), hi = Math.ceil(idx);
  if (lo === hi) return ordenadaAsc[lo];
  return ordenadaAsc[lo] + (ordenadaAsc[hi] - ordenadaAsc[lo]) * (idx - lo);
}

/** Media, mediana, os 5 videos com mais views e os 5 mais recentes (cada um
 * com suas views) de uma lista de videos. Mediana, nao media, resume o
 * "video tipico" - um unico viral distorce a media inteira.
 *
 * outlier_threshold / extreme_threshold: limite de "fora da curva" e "fora da
 * curva de forma insana", pelo metodo de boxplot (Q3 + 1.5x e Q3 + 3x o IQR).
 * NAO e multiplo fixo da mediana (tipo "10x a mediana") - isso quebra num
 * canal pequeno, onde a mediana pode ser tipo 7 views e "10x" vira 70, o que
 * nao significa nada. O metodo por quartil se ajusta sozinho a escala real
 * de CADA canal, seja a mediana 7 ou 7 mil. So calcula com >=4 videos -
 * com menos que isso um quartil nao quer dizer nada (null = "sem dado
 * suficiente pra apontar destaque", nunca um numero inventado). */
function estatisticasVideos_(videos) {
  if (!videos.length) {
    return { total: 0, media_views: 0, mediana_views: 0, melhores: [], recentes: [],
             outlier_threshold: null, extreme_threshold: null };
  }
  var viewsList = videos.map(function (v) { return v.views; }).sort(function (a, b) { return a - b; });
  var soma = viewsList.reduce(function (a, b) { return a + b; }, 0);
  var meio = Math.floor(viewsList.length / 2);
  var mediana = viewsList.length % 2 ? viewsList[meio] : (viewsList[meio - 1] + viewsList[meio]) / 2;
  var ordenados = videos.slice().sort(function (a, b) { return b.views - a.views; });
  var recentes = videos.slice().sort(function (a, b) { return new Date(b.publicado_em) - new Date(a.publicado_em); });

  var outlierThreshold = null, extremeThreshold = null;
  if (viewsList.length >= 4) {
    var q1 = percentil_(viewsList, 0.25), q3 = percentil_(viewsList, 0.75);
    var iqr = q3 - q1;
    outlierThreshold = Math.round(q3 + 1.5 * iqr);
    extremeThreshold = Math.round(q3 + 3 * iqr);
  }

  return {
    total: videos.length,
    media_views: Math.round(soma / videos.length),
    mediana_views: Math.round(mediana),
    melhores: ordenados.slice(0, 5),
    recentes: recentes.slice(0, 5),
    outlier_threshold: outlierThreshold,
    extreme_threshold: extremeThreshold
  };
}

// ---------------------------------------------------------------------------
// HISTORICO (28/09): o site publico (fora do Claude, hospedado no Cloudflare
// Pages) busca este endpoint direto do navegador - ninguem mais precisa
// gravar o historico manualmente. Guardado em Script Properties (nao precisa
// de planilha nem permissao extra): uma chave por canal, JSON pequeno,
// {by_date: {"2026-09-28": {inscritos, views_totais, total_videos}}}.
// ---------------------------------------------------------------------------

var HISTORICO_DIAS_MANTIDOS = 60;

function _hojeUTC_() {
  return Utilities.formatDate(new Date(), 'Etc/UTC', 'yyyy-MM-dd');
}

function lerHistorico_(canal) {
  var raw = PropertiesService.getScriptProperties().getProperty('historico_' + canal);
  if (!raw) return { by_date: {} };
  try {
    var h = JSON.parse(raw);
    if (!h || !h.by_date) return { by_date: {} };
    return h;
  } catch (e) {
    return { by_date: {} };
  }
}

function gravarHistoricoHoje_(canal, stats) {
  var h = lerHistorico_(canal);
  h.by_date[_hojeUTC_()] = {
    inscritos: stats.inscritos,
    views_totais: stats.views_totais,
    total_videos: stats.total_videos
  };
  // poda: so os ultimos HISTORICO_DIAS_MANTIDOS dias (Script Properties tem
  // limite de 9KB por valor - isso nunca chega perto com so 1 numero/dia).
  var datas = Object.keys(h.by_date).sort();
  while (datas.length > HISTORICO_DIAS_MANTIDOS) {
    delete h.by_date[datas.shift()];
  }
  PropertiesService.getScriptProperties().setProperty('historico_' + canal, JSON.stringify(h));
}

/** Gatilho de tempo (1x/dia, ver instalarHistorico) - grava o snapshot de
 * hoje de cada canal. Antes disso dependia do Claude rodar isso na mao. */
function registrarHistoricoDiario() {
  Object.keys(CANAIS).forEach(function (canal) {
    var cfg = CANAIS[canal];
    if (!cfg.ytId) return;
    try {
      gravarHistoricoHoje_(canal, statsCanal_(cfg.ytId));
    } catch (err) {
      Logger.log('historico falhou pra ' + canal + ': ' + err);
    }
  });
}

/** Rode UMA vez (Executar > instalarHistorico): agenda o registro diario as
 * 23h (UTC), ~20h Brasilia - depois que a maior parte dos posts do dia ja saiu. */
function instalarHistorico() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'registrarHistoricoDiario') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('registrarHistoricoDiario').timeBased().everyDays(1).atHour(23).create();
  Logger.log('Historico diario instalado.');
}

function dadosPainel_() {
  var out = { gerado_em: new Date().toISOString(), canais: {} };
  Object.keys(CANAIS).forEach(function (canal) {
    var cfg = CANAIS[canal];
    var bloco = { titulo: cfg.titulo || canal };
    try {
      var fila = listarFilaCompleta_(canal);
      var agora = new Date();
      var futuros = fila.filter(function (i) { return new Date(i.quando) > agora; });
      bloco.fila_total = fila.length;
      bloco.fila_futura = futuros.length;
      bloco.fila_campanha = fila.filter(function (i) { return i.campanha; }).length;
      bloco.proximo = futuros.length ? futuros[0] : null;
      bloco.ultimo_agendado = fila.length ? fila[fila.length - 1] : null;
      bloco.itens = fila;  // lista completa, a pagina decide o que mostrar
      // esperado nas ultimas 24h = itens da fila cujo horario ja passou mas
      // ainda estao aqui (a limpeza so tira depois de 2 dias) - proxy de
      // "devia ter postado".
      var desde = new Date(Date.now() - 24 * 3600 * 1000);
      bloco.esperados_24h = fila.filter(function (i) {
        var q = new Date(i.quando);
        return q <= agora && q > desde;
      }).length;
    } catch (err) {
      bloco.erro_fila = String(err);
    }
    try {
      if (cfg.ytId) {
        var stats = statsCanal_(cfg.ytId);
        bloco.stats = stats;
        bloco.historico = lerHistorico_(canal);
        bloco.postados_24h = postadosRecentes_(stats.uploads_playlist, 26);
        try {
          var todosVideos = listarVideosCanal_(stats.uploads_playlist);
          bloco.video_stats = estatisticasVideos_(todosVideos);
        } catch (errV) {
          bloco.erro_video_stats = String(errV);
        }
      } else {
        bloco.erro_stats = 'sem ytId para este canal';
      }
    } catch (err) {
      bloco.erro_stats = String(err);
    }
    out.canais[canal] = bloco;
  });
  return out;
}
