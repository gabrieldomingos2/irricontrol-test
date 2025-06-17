// assets/js/i18n.js

let translations = {};

async function loadTranslations(lang) {
    try {
        const response = await fetch(`assets/locales/${lang}.json`);
        if (!response.ok) {
            throw new Error(`Could not load ${lang}.json`);
        }
        translations = await response.json();
        console.log(`Translations for ${lang} loaded successfully.`);
    } catch (error) {
        console.error("Failed to load translations, falling back to pt-br:", error);
        const response = await fetch(`assets/locales/pt-br.json`);
        translations = await response.json();
    }
}

function t(key, options = {}) {
    let text = key.split('.').reduce((obj, i) => obj?.[i], translations);

    if (!text) {
        console.warn(`Translation key not found: ${key}`);
        return key;
    }

    Object.keys(options).forEach(placeholder => {
        const regex = new RegExp(`{${placeholder}}`, 'g');
        text = text.replace(regex, options[placeholder]);
    });

    return text;
}

function applyTranslations() {
    document.querySelectorAll('[data-i18n]').forEach(element => {
        const key = element.getAttribute('data-i18n');
        const attribute = element.getAttribute('data-i18n-attr') || 'textContent';

        if (attribute === 'textContent') {
            element.textContent = t(key);
        } else {
            element.setAttribute(attribute, t(key));
        }
    });
    console.log("UI translations applied.");
}

async function setLanguage(lang) {
    await loadTranslations(lang);
    applyTranslations();
    localStorage.setItem('preferredLanguage', lang);
    document.documentElement.lang = lang;
}