# backend/services/i18n_service.py

import json
import logging
from pathlib import Path
from typing import Dict, Callable, Any, Optional, List, Mapping
import threading
import time

from backend.config import settings  # se quiser ler DEFAULT_LANG do settings

logger = logging.getLogger("irricontrol")


# ---------------------- Helpers ----------------------

def _normalize_lang(code: str) -> str:
    """Normaliza código BCP-47 básico (pt-BR → pt-br)."""
    return (code or "").strip().replace("_", "-").lower()


def _lang_variants(code: str) -> List[str]:
    """
    Gera cadeia de variantes do idioma:
        'pt-br' -> ['pt-br', 'pt']
        'en'    -> ['en']
    """
    code = _normalize_lang(code)
    if not code:
        return []
    parts = code.split("-")
    variants = ["-".join(parts[:i]) for i in range(len(parts), 0, -1)]
    return variants


class _SafeDict(dict):
    """dict que não explode em format_map quando falta placeholder; mantém {chave}."""
    def __missing__(self, key):
        return "{" + key + "}"


def _deep_get(d: Mapping[str, Any], keys: List[str]) -> Optional[Any]:
    cur: Any = d
    for k in keys:
        if not isinstance(cur, Mapping):
            return None
        cur = cur.get(k)
        if cur is None:
            return None
    return cur


# ---------------------- Serviço ----------------------

class TranslationService:
    def __init__(self, locales_dir: Path, default_lang: str = 'pt-br', fallback_to_en: bool = True):
        self.locales_dir = locales_dir
        self.default_lang = _normalize_lang(
            getattr(settings, "DEFAULT_LANG", default_lang)
        )
        self.fallback_to_en = fallback_to_en

        self.translations: Dict[str, Dict[str, Any]] = {}
        self._files_mtime: Dict[str, float] = {}
        self._lock = threading.RLock()

        self._load_all_translations()

    # --------- Carregamento / Reload ---------

    def _load_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("Arquivo de tradução não é um objeto JSON na raiz.")
            return data
        except (json.JSONDecodeError, OSError, ValueError) as e:
            logger.error("Falha ao carregar %s: %s", file_path, e)
            return None

    def _load_all_translations(self) -> None:
        """Carrega/recupera todos os .json do diretório de locales."""
        with self._lock:
            if not self.locales_dir.is_dir():
                logger.error("Diretório de locales não encontrado: %s", self.locales_dir)
                return

            count = 0
            for file_path in sorted(self.locales_dir.glob("*.json")):
                lang_code = _normalize_lang(file_path.stem)
                data = self._load_file(file_path)
                if data is None:
                    continue
                self.translations[lang_code] = data
                try:
                    self._files_mtime[str(file_path)] = file_path.stat().st_mtime
                except OSError:
                    pass
                count += 1
                logger.info("Tradução carregada: '%s' (%s)", lang_code, file_path.name)

            if count == 0:
                logger.warning("Nenhuma tradução encontrada em %s", self.locales_dir)

    def reload_if_changed(self) -> None:
        """
        Recarrega somente arquivos alterados (útil em dev).
        Chame isso no startup periódico ou manualmente quando necessário.
        """
        with self._lock:
            for file_path in sorted(self.locales_dir.glob("*.json")):
                key = str(file_path)
                try:
                    mtime = file_path.stat().st_mtime
                except OSError:
                    continue

                prev = self._files_mtime.get(key)
                if prev is None or mtime > prev:
                    data = self._load_file(file_path)
                    if data is not None:
                        lang_code = _normalize_lang(file_path.stem)
                        self.translations[lang_code] = data
                        self._files_mtime[key] = mtime
                        logger.info("Tradução recarregada: '%s' (%s)", lang_code, file_path.name)

    # --------- API Pública ---------

    def set_default_lang(self, code: str) -> None:
        with self._lock:
            self.default_lang = _normalize_lang(code)

    def available_languages(self) -> List[str]:
        with self._lock:
            return sorted(self.translations.keys())

    def _resolve_fallback_chain(self, lang: str) -> List[str]:
        """
        Cadeia de fallback:
            [lang_variants..., default_lang, 'en' se existir e permitido]
        Sem duplicatas e só idiomas carregados.
        """
        with self._lock:
            chain: List[str] = []
            for candidate in _lang_variants(lang):
                if candidate in self.translations and candidate not in chain:
                    chain.append(candidate)

            if self.default_lang and self.default_lang not in chain and self.default_lang in self.translations:
                chain.append(self.default_lang)

            if self.fallback_to_en and "en" in self.translations and "en" not in chain:
                chain.append("en")

            return chain

    def _get_any(self, lang: str, key: str) -> Optional[Any]:
        """
        Busca um valor (pode ser string, objeto, etc.) seguindo a cadeia de fallback.
        Retorna None se não achar em lugar nenhum.
        """
        keys = key.split(".")
        for candidate in self._resolve_fallback_chain(lang):
            val = _deep_get(self.translations.get(candidate, {}), keys)
            if val is not None:
                if candidate != _normalize_lang(lang):
                    logger.debug("Chave '%s' não encontrada em '%s'; usando fallback '%s'.", key, lang, candidate)
                return val
        return None

    def _get_text(self, lang: str, key: str) -> Optional[str]:
        val = self._get_any(lang, key)
        if val is None:
            return None
        if isinstance(val, str):
            return val
        # se não for string, devolve JSON compacto (útil p/ listas/objetos)
        try:
            return json.dumps(val, ensure_ascii=False, separators=(",", ":"))
        except Exception:
            return str(val)

    def get_translator(self, lang_code: str) -> Callable[[str], str]:
        """
        Retorna uma função 't(key, default=None, **kwargs)' que:
            - traduz seguindo os fallbacks,
            - formata com kwargs (placeholders faltantes permanecem {assim}),
            - retorna 'default' se fornecido; senão retorna a própria 'key' como último fallback.
        """
        lang_code = _normalize_lang(lang_code)

        def translator(key: str, default: Optional[str] = None, **kwargs: Any) -> str:
            text = self._get_text(lang_code, key)
            if text is None:
                if default is not None:
                    text = default
                else:
                    logger.error("Chave de tradução '%s' não encontrada (lang='%s', chain=%s).",
                                key, lang_code, self._resolve_fallback_chain(lang_code))
                    text = key  # último fallback: a própria chave

            if kwargs:
                try:
                    # format_map com _SafeDict -> placeholders ausentes ficam como {nome}
                    return text.format_map(_SafeDict(kwargs))
                except Exception as e:
                    logger.error("Erro ao formatar chave '%s' (lang='%s'): %s | texto='%s' | kwargs=%s",
                                key, lang_code, e, text, kwargs)
                    return text
            return text

        return translator


# caminho padrão: backend/services/../locales
_locales_root = Path(__file__).resolve().parent.parent / "locales"

# permite override por settings (opcional)
_locales_dir = Path(getattr(settings, "LOCALES_DIR", _locales_root))

i18n_service = TranslationService(
    locales_dir=_locales_dir,
    default_lang=getattr(settings, "DEFAULT_LANG", "pt-br"),
    fallback_to_en=True,
)
