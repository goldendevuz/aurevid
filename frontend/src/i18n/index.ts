// SPDX-License-Identifier: AGPL-3.0-or-later
import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./locales/en.json";
import ru from "./locales/ru.json";
import uz from "./locales/uz.json";

export const LANGUAGES = [
  { code: "en", label: "English" },
  { code: "uz", label: "O'zbekcha" },
  { code: "ru", label: "Русский" },
] as const;

function initialLanguage(): string {
  try {
    const saved = localStorage.getItem("aurevid.lang"); // UI preference only, never secrets
    if (saved && LANGUAGES.some((l) => l.code === saved)) return saved;
  } catch {
    /* storage unavailable */
  }
  const nav = typeof navigator !== "undefined" ? navigator.language.slice(0, 2) : "en";
  return LANGUAGES.some((l) => l.code === nav) ? nav : "en";
}

void i18n.use(initReactI18next).init({
  resources: { en: { translation: en }, uz: { translation: uz }, ru: { translation: ru } },
  lng: initialLanguage(),
  fallbackLng: "en",
  interpolation: { escapeValue: false }, // React already escapes
});

i18n.on("languageChanged", (lng) => {
  try {
    localStorage.setItem("aurevid.lang", lng);
  } catch {
    /* ignore */
  }
  document.documentElement.lang = lng;
});

export default i18n;
