// Listing Suite → Figma: раскладывает готовые переводы по текстовым слоям.
//
// Последнее звено цикла. REST API Figma на запись не умеет ни на одном
// тарифе — это ограничение самой Figma, — поэтому текст возвращается
// в макет плагином, который дизайнер запускает в открытом файле.
//
// СВЯЗКА ПО `slot`, НЕ ПО `layer_id`. Идентификаторы узлов на языковых
// страницах другие, а имена фреймов и пути в дереве совпадают —
// проверено на живом файле: 33 из 33 слотов B0G4S9SJ3M сходятся на
// UK/US и DE, «Battery Capacity» и «Batteriekapazität» лежат в одном
// месте `PT01#0.1.2`. `layer_id` из выгрузки указывает на английский
// слой и на языковой странице не существует.
//
// ОБХОД ОБЯЗАН СОВПАДАТЬ С services/figma.py::_walk_text. Разойдётся —
// переводы встанут не в те строки, и это худший исход: выглядит
// правдоподобно. Правило одно и простое: `slot` = имя ВЕРХНЕГО фрейма
// + `#` + индексы детей на каждом уровне через точку, считаются ВСЕ
// дети (картинки, группы, скрытые), а не только текстовые; строку
// даёт только TEXT с непустым текстом. Совпадение обхода с Python
// проверяет tests/test_figma_plugin.py на одном дереве.
//
// Чего плагин НЕ делает: не трогает картинки, не меняет шрифт и кегль,
// не создаёт слои (нет слоя — сообщает), не применяет молча (сначала
// план, потом кнопка, потом отчёт с числами).

// ---- общее с services/figma.py — держать в синхроне (проверяется тестом)
var PAGE_LANG = { "UK/US": "en", "DE": "de", "ES": "es", "IT": "it", "FR": "fr" };
// одна-две лишние буквы перед ASIN допускаются: в файле есть BB0GJMT58WT.MAIN
var FRAME_RE = /^([A-Z]{0,2})(B0[A-Z0-9]{8})\.(.+)$/;

// Рекурсивный обход — зеркало _walk_text. Работает и с узлами
// плагина, и с JSON REST API: у обоих `type`, `name`, `children`,
// `characters` — этим и пользуется тест.
function walkText(node, out, frame, path) {
  if (!node) return;
  if (node.type === "TEXT") {
    var text = String(node.characters || "").trim();
    if (text) out.push({ node: node, slot: frame + "#" + path.join("."), text: text });
  }
  var kids = node.children || [];
  for (var i = 0; i < kids.length; i++) walkText(kids[i], out, frame, path.concat(i));
}

// Все текстовые слои страницы по слоту. Значение — СПИСОК: два фрейма
// с одним именем дали бы один slot на два слоя, и подставлять в такой
// нельзя — это надо назвать, а не выбрать первый попавшийся.
function indexPage(page) {
  var bySlot = {};
  var frames = page.children || [];
  for (var i = 0; i < frames.length; i++) {
    var fr = frames[i];
    if (fr.type !== "FRAME") continue;          // подписи и прочее — мимо, как в Python
    var found = [];
    walkText(fr, found, String(fr.name || ""), []);
    for (var j = 0; j < found.length; j++) {
      var s = found[j].slot;
      (bySlot[s] = bySlot[s] || []).push(found[j]);
    }
  }
  return bySlot;
}

// Имя фрейма без опечатки: `BB0GJMT58WT.MAIN` → `B0GJMT58WT.MAIN`.
// Нужно, когда на языковой странице фрейм назван с лишней буквой,
// а на английской — без (или наоборот): слот из выгрузки тогда не
// совпадёт буквально, но макет тот же.
function normFrame(name) {
  var m = FRAME_RE.exec(name);
  return m ? m[2] + "." + m[3] : name;
}

function slotFrame(slot) { return slot.split("#")[0]; }

// План: что с каждой строкой выгрузки будет сделано. Ничего не меняет.
//   replace   — слой найден, текст другой → заменим
//   same      — слой найден, текст уже такой → трогать нечего
//   missing   — слоя с таким slot на странице нет
//   ambiguous — слотов несколько (два фрейма с одним именем)
//   mixed     — в слое несколько шрифтов/кеглей: простая замена их
//               потеряет, пропускаем и говорим об этом
function buildPlan(bySlot, layers, isMixed) {
  // второй индекс — по нормализованному имени фрейма, для опечаток
  var byNorm = {};
  Object.keys(bySlot).forEach(function (s) {
    var k = normFrame(slotFrame(s)) + "#" + s.split("#")[1];
    byNorm[k] = (byNorm[k] || []).concat(bySlot[s]);
  });
  var rows = [];
  for (var i = 0; i < layers.length; i++) {
    var L = layers[i];
    var slot = String(L.slot || "");
    var want = String(L.text || "").trim();
    var hits = bySlot[slot];
    var viaTypo = false;
    if (!hits || !hits.length) {
      var k = normFrame(slotFrame(slot)) + "#" + slot.split("#")[1];
      hits = byNorm[k];
      viaTypo = !!(hits && hits.length);
    }
    var row = { slot: slot, want: want, now: "", state: "missing", typo: viaTypo, node: null };
    if (!want) { row.state = "empty"; rows.push(row); continue; }
    if (!hits || !hits.length) { rows.push(row); continue; }
    if (hits.length > 1) { row.state = "ambiguous"; rows.push(row); continue; }
    row.node = hits[0].node;
    row.now = hits[0].text;
    if (isMixed && isMixed(row.node)) row.state = "mixed";
    else row.state = (row.now === want) ? "same" : "replace";
    rows.push(row);
  }
  return rows;
}

function summarize(rows) {
  var s = { replace: 0, same: 0, missing: 0, ambiguous: 0, mixed: 0, empty: 0 };
  rows.forEach(function (r) { s[r.state] = (s[r.state] || 0) + 1; });
  return s;
}

// ---- сторона Figma. Ниже — только то, что требует figma.*
function findPage(lang) {
  var pages = figma.root.children;
  for (var i = 0; i < pages.length; i++) {
    if (PAGE_LANG[pages[i].name] === lang) return pages[i];
  }
  return null;
}

function isMixedFont(node) {
  return node.fontName === figma.mixed;
}

function stripNodes(rows) {
  // в UI узлы не передать — только описание
  return rows.map(function (r) {
    return { slot: r.slot, want: r.want, now: r.now, state: r.state, typo: r.typo };
  });
}

var PLAN = null;      // план последнего разбора, применяется по кнопке

async function plan(payload) {
  var lang = String(payload.lang || "");
  var layers = payload.layers || [];
  var warnings = [];

  if (figma.fileKey && payload.file_key && figma.fileKey !== payload.file_key) {
    warnings.push("Файл выгрузки (" + payload.file_key + ") не совпадает с открытым (" + figma.fileKey + ").");
  }
  var page = findPage(lang);
  if (!page) {
    return { ok: false, error: "Языковой страницы для «" + lang.toUpperCase() +
      "» в файле нет. Копирование макета на новую страницу — следующий шаг, " +
      "пока плагин работает только с готовыми языковыми страницами." };
  }
  await page.loadAsync();                       // dynamic-page: дети страницы грузятся по запросу
  var bySlot = indexPage(page);
  var rows = buildPlan(bySlot, layers, isMixedFont);
  PLAN = { page: page, rows: rows, lang: lang, asin: payload.asin };
  return {
    ok: true, page: page.name, file: figma.root.name, asin: payload.asin,
    lang: lang, rows: stripNodes(rows), summary: summarize(rows), warnings: warnings
  };
}

async function apply() {
  if (!PLAN) return { ok: false, error: "Сначала загрузите выгрузку." };
  var done = 0, failed = [];
  var rows = PLAN.rows;
  for (var i = 0; i < rows.length; i++) {
    var r = rows[i];
    if (r.state !== "replace") continue;
    var node = r.node;
    try {
      if (node.hasMissingFont) throw new Error("шрифт слоя не установлен");
      // Шрифт грузится ИМЕННО этого слоя: без loadFontAsync Figma
      // отказывает менять characters. Смешанные слои сюда не доходят.
      await figma.loadFontAsync(node.fontName);
      node.characters = r.want;
      done += 1;
    } catch (e) {
      failed.push({ slot: r.slot, error: String(e && e.message || e) });
    }
  }
  var s = summarize(rows);
  var report = {
    ok: true, replaced: done, same: s.same,
    missing: rows.filter(function (r) { return r.state === "missing"; }).map(function (r) { return r.slot; }),
    ambiguous: rows.filter(function (r) { return r.state === "ambiguous"; }).map(function (r) { return r.slot; }),
    mixed: rows.filter(function (r) { return r.state === "mixed"; }).map(function (r) { return r.slot; }),
    failed: failed
  };
  figma.notify("Listing Suite: заменено " + done + ", не найдено " + report.missing.length);
  return report;
}

function main() {
  figma.showUI(__html__, { width: 640, height: 560, title: "Listing Suite: перевод в макет" });
  figma.ui.onmessage = async function (msg) {
    try {
      if (msg.type === "plan") figma.ui.postMessage({ type: "plan", result: await plan(msg.payload) });
      else if (msg.type === "apply") figma.ui.postMessage({ type: "report", result: await apply() });
      else if (msg.type === "close") figma.closePlugin();
    } catch (e) {
      figma.ui.postMessage({ type: "error", error: String(e && e.message || e) });
    }
  };
}

// В песочнице Figma `figma` есть, в тесте (JavaScriptCore / Node) — нет:
// там нужны только чистые функции обхода и плана.
if (typeof figma !== "undefined") main();
if (typeof module !== "undefined") {
  module.exports = { PAGE_LANG: PAGE_LANG, FRAME_RE: FRAME_RE, walkText: walkText,
    indexPage: indexPage, buildPlan: buildPlan, summarize: summarize, normFrame: normFrame };
}
