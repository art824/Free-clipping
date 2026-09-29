/**
 * Pensa Como Dono - fila de postagem do YouTube (roda na nuvem do Google, gratis).
 *
 * COMO FUNCIONA
 *  - O PC copia cada clipe (.mp4) + um .json (titulo, descricao, horario) pra
 *    "Meu Drive/PensaComoDono/fila". O Google Drive pra Desktop sobe sozinho.
 *  - Este script publica um feed RSS que so mostra os clipes cujo horario JA chegou.
 *  - O Zapier (gratis) le o feed a cada 15 min e sobe cada item novo no YouTube.
 *    Como o app de YouTube do Zapier e verificado, o video sai publico.
 *    (Upload direto daqui do Apps Script ficaria travado como privado.)
 *  - limpar() manda pra lixeira os clipes que ja passaram do horario ha 2+ dias.
 *
 * INSTALAR (uma vez)
 *  1. Implantar > Nova implantacao > tipo "App da Web"
 *       Executar como: Eu     |     Quem pode acessar: Qualquer pessoa
 *  2. Copie a URL que termina em /exec  -> e ela que vai no Zapier.
 *  3. Rode a funcao instalarLimpeza uma vez (menu de funcoes > Executar).
 */

var PASTA = 'PensaComoDono/fila';   // caminho dentro do "Meu Drive"
var DIAS_ATE_LIMPAR = 2;
var MAX_ITENS = 25;

function doGet(e) {
  var itens = itensVencidos_(new Date());
  var xml = montarFeed(itens, ScriptApp.getService().getUrl());
  return ContentService.createTextOutput(xml).setMimeType(ContentService.MimeType.RSS);
}

/** Rode no editor pra ver o feed no log (Executar > testarFeed > Registro de execucao). */
function testarFeed() {
  var itens = itensVencidos_(new Date());
  Logger.log(itens.length + ' clipe(s) liberado(s) no feed agora');
  Logger.log(montarFeed(itens, 'teste'));
}

function pasta_() {
  var atual = DriveApp.getRootFolder();
  var partes = PASTA.split('/');
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

function itensVencidos_(agora) {
  var pasta = pasta_();
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
function montarFeed(itens, urlBase) {
  var p = [];
  p.push('<?xml version="1.0" encoding="UTF-8"?>');
  p.push('<rss version="2.0"><channel>');
  p.push('<title>Pensa Como Dono - fila</title>');
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

/** Lixeira pros clipes cujo horario passou ha mais de DIAS_ATE_LIMPAR dias. */
function limpar() {
  var pasta = pasta_();
  if (!pasta) return;
  var limite = new Date(Date.now() - DIAS_ATE_LIMPAR * 24 * 3600 * 1000);
  var jsons = [];
  var arquivos = pasta.getFiles();
  while (arquivos.hasNext()) {
    var f = arquivos.next();
    if (/\.json$/i.test(f.getName())) jsons.push(f);
  }
  var removidos = 0;
  jsons.forEach(function (j) {
    var meta = lerMeta_(j);
    if (!meta) return;
    var quando = new Date(meta.publicar_em);
    if (isNaN(quando.getTime()) || quando > limite) return;
    var base = j.getName().replace(/\.json$/i, '');
    var vids = pasta.getFilesByName(base + '.mp4');
    while (vids.hasNext()) { vids.next().setTrashed(true); }
    j.setTrashed(true);
    removidos++;
  });
  Logger.log(removidos + ' clipe(s) antigos mandados pra lixeira');
}

/** Rode UMA vez: agenda o limpar() todo dia as 4h. */
function instalarLimpeza() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'limpar') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('limpar').timeBased().everyDays(1).atHour(4).create();
  Logger.log('Limpeza diaria instalada.');
}

if (typeof module !== 'undefined') {
  module.exports = { montarFeed: montarFeed, esc_: esc_ };
}
