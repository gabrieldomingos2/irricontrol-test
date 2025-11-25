// assets/js/i18n.js

// ===== Config =====
const DEFAULT_LANG = "pt-br";
const SAFE_ATTRS = new Set([
  "title",
  "placeholder",
  "aria-label",
  "aria-describedby",
  "aria-controls",
  "alt",
  "value", // cuidado: só use quando fizer sentido (ex.: <input value>)
  "data-label",
]);

let currentLanguage = DEFAULT_LANG;
const translationsCache = new Map(); // lang -> dict
let activeDict = {}; // dicionário em uso (merge de fallback + lang)

// ===== Utils =====
function normalizeLang(input) {
  if (!input) return DEFAULT_LANG;
  const s = String(input).toLowerCase();
  // mapeamentos simples/comuns
  if (s.startsWith("pt")) return "pt-br";
  if (s.startsWith("en")) return "en";
  if (s.startsWith("es")) return "es";
  if (s.startsWith("de")) return "de";
  if (s.startsWith("ru")) return "ru";
  return DEFAULT_LANG;
}

function getNested(obj, path) {
  return path
    .split(".")
    .reduce((acc, k) => (acc && typeof acc === "object" ? acc[k] : undefined), obj);
}

function deepMerge(target, source) {
  const out = Array.isArray(target) ? [...target] : { ...target };
  if (!source || typeof source !== "object") return out;
  for (const [k, v] of Object.entries(source)) {
    if (v && typeof v === "object" && !Array.isArray(v)) {
      out[k] = deepMerge(out[k] || {}, v);
    } else {
      out[k] = v;
    }
  }
  return out;
}

// Interpola {placeholders}
function interpolate(str, options = {}) {
  if (typeof str !== "string") return str;
  return Object.keys(options).reduce((txt, key) => {
    const re = new RegExp(`\\{${key}\\}`, "g");
    return txt.replace(re, String(options[key]));
  }, str);
}

function _isValueAssignable(el) {
  const tag = el.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
}

// ===== Carregamento =====
async function fetchLocaleDict(lang) {
  if (translationsCache.has(lang)) return translationsCache.get(lang);

  const base =
    (typeof window.I18N_LOCALES_BASE === "string" && window.I18N_LOCALES_BASE) ||
    "assets/locales";
  const url = `${base.replace(/\/+$/, "")}/${lang}.json`;

  try {
    const res = await fetch(url, { cache: "no-cache" });
    if (!res.ok) throw new Error(`Could not load ${lang}.json`);
    const json = await res.json();
    translationsCache.set(lang, json);
    console.log(`i18n: ${lang} carregado.`);
    return json;
  } catch (err) {
    console.warn(`i18n: falha ao carregar ${lang}.json ->`, err);
    translationsCache.set(lang, {}); // evita retries em loop
    return {};
  }
}

async function loadTranslations(lang) {
  const langNorm = normalizeLang(lang);
  const isDefault = langNorm === DEFAULT_LANG;

  const fallbackDict = await fetchLocaleDict(DEFAULT_LANG);
  const langDict = isDefault ? fallbackDict : await fetchLocaleDict(langNorm);

  // merge profundo para preencher chaves ausentes
  activeDict = isDefault ? fallbackDict : deepMerge(fallbackDict, langDict);
  currentLanguage = langNorm;
}

// ===== API pública =====
function t(key, options = {}) {
  let text = getNested(activeDict, key);
  if (text == null) {
    // fallback: retorna a própria chave e avisa
    console.warn(`i18n: chave não encontrada '${key}' em ${currentLanguage}`);
    return interpolate(key, options);
  }
  return interpolate(text, options);
}

// Aplica em 1 elemento (útil para componentes dinâmicos)
function applyTranslationTo(el) {
  const key = el.getAttribute("data-i18n");
  if (!key) return;

  // argumentos opcionais em JSON no atributo (parser blindado)
  let args = {};
  const argsAttr = el.getAttribute("data-i18n-args");
  if (argsAttr) {
    let raw = String(argsAttr).trim();

    // só aceitamos algo que pareça JSON de verdade
    if (raw.startsWith("{") || raw.startsWith("[")) {
      try {
        args = JSON.parse(raw);
      } catch (e) {
        console.warn("i18n: data-i18n-args inválido. Ignorando:", raw, e, el);
        args = {};
      }
    } else {
      console.warn("i18n: data-i18n-args não parece JSON. Ignorando:", raw, el);
    }
  }

  const attrList = (el.getAttribute("data-i18n-attr") || "textContent")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);

  // Se houver vários atributos, aplica em cada um; textContent é o padrão.
  for (const attr of attrList) {
    if (attr === "textContent") {
      // evita HTML injection
      el.textContent = t(key, args);
    } else {
      // só permite atributos "seguros"
      if (!SAFE_ATTRS.has(attr)) {
        console.warn(`i18n: atributo não permitido "${attr}" para chave '${key}'`, el);
        continue;
      }
      if (attr === "value" && !_isValueAssignable(el)) {
        console.warn(
          `i18n: atributo "value" ignorado em <${el.tagName.toLowerCase()}> para chave '${key}'`
        );
        continue;
      }
      el.setAttribute(attr, t(key, args));
    }
  }
}

function applyTranslations(root = document) {
  const nodes = root.querySelectorAll("[data-i18n]");
  nodes.forEach(applyTranslationTo);

  // Ajustes espec��ficos de tooltip que n��o usam data-i18n diretamente
  const resetButton = document.getElementById("resetar-btn");
  if (resetButton) {
    resetButton.setAttribute("title", t("tooltips.reset"));
  }

  // Título do documento (caso exista <title data-i18n="...">)
  const titleEl = document.querySelector("head title[data-i18n]");
  if (titleEl) document.title = titleEl.textContent;

  // Emite evento para quem quiser ouvir
  document.dispatchEvent(
    new CustomEvent("i18n:applied", { detail: { lang: currentLanguage } })
  );
  console.log(`i18n: traduções aplicadas (${currentLanguage}).`);
}

// Troca de idioma completa
async function setLanguage(lang) {
  await loadTranslations(lang);
  applyTranslations();
  localStorage.setItem("preferredLanguage", currentLanguage);
  document.documentElement.lang = currentLanguage;
  // (Opcional) RTL/LTR — se suportar idiomas RTL no futuro
  document.documentElement.dir = "ltr";
}

// Inicializa: descobre idioma e conecta botões [data-lang]
async function initI18n() {
  const saved = localStorage.getItem("preferredLanguage");
  const browser = normalizeLang(navigator.language || navigator.userLanguage);
  const initial = saved || browser || DEFAULT_LANG;

  await setLanguage(initial);

  // Botões de troca de idioma
  document.querySelectorAll("[data-lang]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const lang = btn.getAttribute("data-lang");
      setLanguage(lang);
    });
  });
}

// Exponha no global para uso em outros módulos
window.t = t;
window.setLanguage = setLanguage;
window.applyTranslations = applyTranslations;
window.getCurrentLanguage = () => currentLanguage;

// Auto-init após DOM pronto (scripts estão no final do body; ainda assim garantimos)
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initI18n, { once: true });
} else {
  initI18n();
}
