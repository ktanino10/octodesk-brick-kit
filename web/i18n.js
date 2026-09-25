const data = window.OCTODESK_DATA;
let language = new URLSearchParams(location.search).get("lang") === "en" ? "en" : "ja";
const nodes = [...document.querySelectorAll("[data-en]")].map((element) => ({
  element, ja: element.innerHTML, en: element.dataset.en
}));
const attributes = [...document.querySelectorAll("[data-en-alt], [data-en-aria-label]")].flatMap((element) =>
  ["alt", "aria-label"].filter((name) => element.hasAttribute(`data-en-${name}`)).map((name) => ({
    element, name, ja: element.getAttribute(name), en: element.getAttribute(`data-en-${name}`)
  })));
const messages = {
  ja: {
    loadError: "3Dガイドを読み込めませんでした: {detail}。PDFとCSVは利用できます。",
    parts: "{n}個", step: "工程{n}", equivalents: "同形同色 {n}個",
    assembled: "{n} / {total}個", dimensions: "完成寸法 mm（スタッド・耳を含む）",
    types: "個 / {n}型", colors: "工程 / {n}色", zero: "0 · 空の机",
    complete: "完成 / {total}個・{steps}工程。部品をクリックすると取り出し元を表示します。",
    empty: "0個配置済み / 空の机です。\n「次の1個」で {first} の取り付けを始めます。",
    physical: "現物の嵌合・保持力・強度・反り・転倒・耐久性は未評価です。",
    foundation: "台座の手前は−Y。最初の6枚は机に並べ、上段で連結します。",
    placement: "{role} · 下角({position}) mm · Z回転{angle}° · 上から↓",
    captionIdle: "動画を再生すると、ここに工程と追加する個体IDを表示します。"
  },
  en: {
    loadError: "The 3D guide could not load: {detail}. The PDF and CSV files remain available.",
    parts: "{n} parts", step: "Step {n}", equivalents: "{n} interchangeable parts of this type/color",
    assembled: "{n} / {total} parts", dimensions: "Finished size in mm, including studs and ears",
    types: "parts / {n} types", colors: "steps / {n} colors", zero: "0 · Empty table",
    complete: "Complete / {total} parts, {steps} steps. Click a part to see every print source.",
    empty: "0 parts placed / the table is empty.\nUse “Next part” to start placing {first}.",
    physical: "Physical fit, retention, strength, warping, tip-over and durability are untested.",
    foundation: "The front of the base is −Y. Arrange the first six plates on the table, then connect them with the upper layer.",
    placement: "{role} · Lower corner ({position}) mm · Z rotation {angle}° · Insert from above ↓",
    captionIdle: "Play the video to see the current step and the instance IDs being added."
  }
};

export const lang = () => language;
export function text(key, values = {}) {
  if (language === "en" && values.n === 1 && key === "parts") return "1 part";
  if (language === "en" && values.n === 1 && key === "equivalents") return "1 matching part of this type/color";
  const template = messages[language][key];
  if (template === undefined) throw new Error(`Missing ${language} message: ${key}`);
  return template.replace(/\{(\w+)\}/g, (_, name) => {
    if (!(name in values)) throw new Error(`Missing message value: ${name}`);
    return String(values[name]);
  });
}
export function stepText(number) {
  const translated = language === "en" ? data.translations.en.steps[number] : data.kit.steps[number - 1];
  if (!translated) throw new Error(`Missing ${language} step ${number}`);
  return translated;
}
export function colorName(id) {
  return language === "en" ? data.translations.en.colors[id] : data.kit.colors[id].name;
}
export function roleName(name) {
  const result = language === "en" ? data.translations.en.roles[name] : name;
  if (!result) throw new Error(`Missing ${language} role`);
  return result;
}
export function applyLanguage(next = language, updateUrl = false) {
  if (next !== "ja" && next !== "en") throw new Error("Unsupported language");
  language = next;
  document.documentElement.lang = next;
  for (const node of nodes) node.element.innerHTML = node[next];
  for (const item of attributes) item.element.setAttribute(item.name, item[next]);
  for (const button of document.querySelectorAll("[data-language]")) {
    button.setAttribute("aria-pressed", String(button.dataset.language === next));
  }
  for (const link of document.querySelectorAll("[data-manual-link]")) {
    link.href = next === "en" ? "docs/assembly-manual.en.pdf" : "docs/assembly-manual.pdf";
  }
  for (const link of document.querySelectorAll("[data-notices-link]")) {
    link.href = next === "en" ? "docs/notices.en.html" : "docs/notices.html";
  }
  for (const link of document.querySelectorAll("[data-subtitle-link]")) {
    link.href = next === "en" ? "media/assembly.en.srt" : "media/assembly.srt";
  }
  if (updateUrl) {
    const url = new URL(location.href);
    url.searchParams.set("lang", next);
    history.replaceState(history.state, "", url.href);
  }
}
