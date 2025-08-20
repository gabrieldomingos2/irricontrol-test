# backend/config.py

# Importações de bibliotecas padrão
import os
import logging
from pathlib import Path
from enum import Enum

# Importações de tipos e Pydantic
from typing import List, Optional, Dict, Any
from pydantic import Field, HttpUrl, BaseModel, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Obter a instância do logger configurado
logger = logging.getLogger("irricontrol")


# --- Modelos Pydantic para estruturas aninhadas ---
class TransmitterSettings(BaseModel):
    model_config = {"frozen": True}
    txw: float = Field(gt=0, description="Potência de transmissão em Watts (>0)")
    bwi: float = Field(ge=0, description="Largura de banda (>=0)")


class ReceiverSettings(BaseModel):
    model_config = {"frozen": True}
    lat: float = Field(default=0.0, ge=-90, le=90)
    lon: float = Field(default=0.0, ge=-180, le=180)
    alt: int = Field(default=3, ge=0)
    rxg: float = Field(gt=0)
    rxs: int = Field(le=0, description="Sensibilidade (dBm) deve ser <= 0")


class AntennaSettings(BaseModel):
    model_config = {"frozen": True}
    txg: float = Field(ge=0)
    fbr: float = Field(ge=0)


class TemplateSettings(BaseModel):
    model_config = {"frozen": True}
    id: str
    nome: str
    frq: int = Field(ge=100, le=6000, description="Frequência em MHz (100–6000)")
    col: str
    site: str
    rxs: int
    transmitter: TransmitterSettings
    receiver: ReceiverSettings
    antenna: AntennaSettings


# Enum para os IDs dos templates para evitar erros de digitação
class TemplateID(str, Enum):
    """Define os identificadores únicos para cada template de simulação."""
    BRAZIL_V6_100DBM = "Brazil_V6_100dBm"
    EUROPE_V6_XR = "Europe_V6_XR"
    BRAZIL_V6_90DBM = "Brazil_V6_90dBm"


# --- Dicionário de Internacionalização (i18n) ---
I18N_KEYWORDS: Dict[str, Dict[str, List[str]]] = {
    "ANTENA": {
        "pt": ["antena", "torre", "central", "base", "repetidora", "barracão", "galpão", "silo", "caixa", "caixa d'água", "poste"],
        "en": ["antenna", "tower", "base", "station", "repeater", "radio", "site", "shed", "warehouse", "silo", "water tank", "pole", "post"],
        "es": ["antena", "torre", "base", "estación", "repetidora", "radio", "cobertizo", "galpón", "almacén", "silo", "tanque de agua", "depósito de agua", "poste"],
        "de": ["antenne", "turm", "basisstation", "repeater", "funkmast", "schuppen", "lagerhalle", "silo", "wassertank", "mast", "pfosten"],
        "ru": ["антенна", "башня", "станция", "репитер", "радиостанция", "сарай", "ангар", "склад", "силос", "водяной бак", "водонапорная башня", "столб", "мачта"]
    },
    "PIVO": {
        "pt": ["pivô", "pivo"],
        "en": ["pivot", "sprinkler"],
        "es": ["pivote", "aspersor"],
        "de": ["pivot", "drehpunkt", "beregnung"],
        "ru": ["пивот", "ороситель", "спринклер"]
    },
    "BOMBA": {
        "pt": ["bomba", "irripump", "pump", "captação", "poço"],
        "en": ["pump", "pumping station", "irripump", "water intake", "well"],
        "es": ["bomba", "estación de bombeo", "irripump", "captación", "toma de agua", "pozo"],
        "de": ["pumpe", "pumpstation", "irripump", "wasserentnahme", "brunnen"],
        "ru": ["насос", "насосная станция", "irripump", "водозабор", "колодец", "скважина"]
    }
}


# --- Defaults seguros de templates (evita estado global mutável) ---
def _default_templates() -> List[Dict[str, Any]]:
    return [
        {
            "id": "Brazil_V6_100dBm",
            "nome": "🇧🇷 Brazil V6 100dBm",
            "frq": 915,
            "col": "IRRICONTRO.dBm",
            "site": "Brazil_V6_100dBm",
            "rxs": -100,
            "transmitter": {"txw": 0.3, "bwi": 0.1},
            "receiver": {"lat": 0, "lon": 0, "alt": 3, "rxg": 3, "rxs": -100},
            "antenna": {"txg": 3, "fbr": 3},
        },
        {
            "id": "Europe_V6_XR",
            "nome": "🇪🇺 Europe V6 XR",
            "frq": 868,
            "col": "IRRIEUROPE.dBm",
            "site": "Europe_V6_XR",
            "rxs": -105,
            "transmitter": {"txw": 0.02, "bwi": 0.05},
            "receiver": {"lat": 0, "lon": 0, "alt": 3, "rxg": 2.1, "rxs": -105},
            "antenna": {"txg": 2.1, "fbr": 2.1},
        },
        {
            "id": "Brazil_V6_90dBm",
            "nome": "Brazil V6 90dBm",
            "frq": 915,
            "col": "CONTROL90.dBm",
            "site": "Brazil_V6_90dBm",
            "rxs": -90,
            "transmitter": {"txw": 0.3, "bwi": 0.1},
            "receiver": {"lat": 0, "lon": 0, "alt": 3, "rxg": 3, "rxs": -90},
            "antenna": {"txg": 3, "fbr": 3},
        },
    ]


# --- Classe Principal de Configurações ---
class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Configurações Gerais da Aplicação ---
    APP_NAME: str = "Irricontrol Signal Simulator API"
    APP_VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # Centraliza a definição do template padrão
    DEFAULT_TEMPLATE_ID: TemplateID = TemplateID.BRAZIL_V6_100DBM

    # --- Configurações de CORS ---
    ALLOWED_ORIGINS_CSV: str = Field(
        default=(
            "http://localhost,"
            "http://localhost:8080,"
            "http://127.0.0.1,"
            "http://127.0.0.1:8080,"
            "null,"
            "http://localhost:5173"
        )
    )
    NETLIFY_APP_URL: Optional[str] = None
    BACKEND_PUBLIC_URL: Optional[HttpUrl] = None

    @property
    def ALLOWED_ORIGINS(self) -> List[str]:
        raw = [o.strip() for o in self.ALLOWED_ORIGINS_CSV.split(",") if o.strip()]
        extras = []
        if self.NETLIFY_APP_URL:
            extras.append(self.NETLIFY_APP_URL.strip().rstrip("/"))
        if self.BACKEND_PUBLIC_URL:
            extras.append(str(self.BACKEND_PUBLIC_URL).strip().rstrip("/"))
        # normaliza e deduplica de forma determinística
        norm = {o.lower().rstrip("/") for o in [*raw, *extras] if o}
        return sorted(norm)

    # --- Configurações de Diretórios ---
    BACKEND_DIR: Path = Path(__file__).resolve().parent
    PROJECT_ROOT_DIR: Path = BACKEND_DIR.parent
    STATIC_DIR_NAME: str = "static"
    IMAGENS_DIR_NAME: str = "imagens"
    ARQUIVOS_DIR_NAME: str = "arquivos"
    CACHE_DIR_NAME: str = "cache"
    SIMULATIONS_CACHE_DIR_NAME: str = "simulations"
    ELEVATION_CACHE_DIR_NAME: str = "elevation"

    @property
    def STATIC_DIR_PATH(self) -> Path:
        return self.BACKEND_DIR / self.STATIC_DIR_NAME

    @property
    def IMAGENS_DIR_PATH(self) -> Path:
        return self.STATIC_DIR_PATH / self.IMAGENS_DIR_NAME

    @property
    def ARQUIVOS_DIR_PATH(self) -> Path:
        return self.BACKEND_DIR / self.ARQUIVOS_DIR_NAME

    @property
    def SIMULATIONS_CACHE_PATH(self) -> Path:
        return self.ARQUIVOS_DIR_PATH / self.CACHE_DIR_NAME / self.SIMULATIONS_CACHE_DIR_NAME

    @property
    def ELEVATION_CACHE_PATH(self) -> Path:
        return self.ARQUIVOS_DIR_PATH / self.CACHE_DIR_NAME / self.ELEVATION_CACHE_DIR_NAME

    @property
    def ENTITY_KEYWORDS(self) -> Dict[str, List[str]]:
        consolidated: Dict[str, List[str]] = {}
        for entity, lang_map in I18N_KEYWORDS.items():
            all_keywords = [w.strip() for words in lang_map.values() for w in words if w.strip()]
            consolidated[entity] = sorted(set(all_keywords))
        return consolidated

    # --- Configurações de API Externa (CloudRF) ---
    CLOUDRF_API_KEY: Optional[str] = None
    CLOUDRF_API_URL: HttpUrl = Field(default="https://api.cloudrf.com/area")
    HTTP_TIMEOUT: float = 60.0
    LOG_LEVEL: str = "INFO"

    @property
    def LOG_LEVEL_INT(self) -> int:
        return getattr(logging, str(self.LOG_LEVEL).upper(), logging.INFO)

    # --- Templates de Simulação Pré-definidos ---
    TEMPLATES_DISPONIVEIS: List[TemplateSettings] = Field(default_factory=_default_templates)

    # --- Métodos de Inicialização e Utilitários ---
    def initialize_directories(self) -> None:
        """Garante que os diretórios necessários para a aplicação existam."""
        logger.info("Verificando/Criando diretório de imagens em: %s", self.IMAGENS_DIR_PATH)
        self.IMAGENS_DIR_PATH.mkdir(parents=True, exist_ok=True)

        logger.info("Verificando/Criando diretório de arquivos em: %s", self.ARQUIVOS_DIR_PATH)
        self.ARQUIVOS_DIR_PATH.mkdir(parents=True, exist_ok=True)

        logger.info(
            "Verificando/Criando diretório de cache de simulações em: %s",
            self.SIMULATIONS_CACHE_PATH,
        )
        self.SIMULATIONS_CACHE_PATH.mkdir(parents=True, exist_ok=True)

        logger.info(
            "Verificando/Criando diretório de cache de elevação em: %s",
            self.ELEVATION_CACHE_PATH,
        )
        self.ELEVATION_CACHE_PATH.mkdir(parents=True, exist_ok=True)

        if not self.CLOUDRF_API_KEY:
            logger.warning("ALERTA DE SEGURANÇA: CLOUDRF_API_KEY não está definida!")
        if not self.BACKEND_PUBLIC_URL:
            logger.warning(
                "ALERTA DE CONFIGURAÇÃO: BACKEND_PUBLIC_URL não está definida! As URLs de imagem podem estar incorretas."
            )

    # Método atualizado para usar o Enum e o ID padrão centralizado
    def obter_template(self, template_id: str | TemplateID) -> TemplateSettings:
        """Busca um template por ID, retornando um padrão se não for encontrado."""
        # Garante que estamos comparando a string do ID
        id_value = template_id.value if isinstance(template_id, TemplateID) else str(template_id)

        template_obj = next((t for t in self.TEMPLATES_DISPONIVEIS if t.id == id_value), None)

        if not template_obj:
            logger.warning(
                "Template '%s' não encontrado. Usando padrão '%s'.",
                id_value,
                self.DEFAULT_TEMPLATE_ID.value,
            )
            default_t = next(
                (t for t in self.TEMPLATES_DISPONIVEIS if t.id == self.DEFAULT_TEMPLATE_ID.value),
                None,
            )
            if default_t:
                return default_t
            # Fallback final: erro explícito com contexto
            raise KeyError(
                f"Template '{id_value}' não encontrado e default '{self.DEFAULT_TEMPLATE_ID.value}' ausente."
            )

        return template_obj

    def listar_templates_ids(self) -> List[str]:
        """Retorna uma lista com os IDs (strings) de todos os templates disponíveis."""
        return [t.id for t in self.TEMPLATES_DISPONIVEIS]

    # --- Validações pós-init (consistência de templates) ---
    @model_validator(mode="after")
    def _validate_templates(self):
        ids = [t.id for t in self.TEMPLATES_DISPONIVEIS]
        if len(ids) != len(set(ids)):
            dupes = sorted({i for i in ids if ids.count(i) > 1})
            raise ValueError(f"IDs de template duplicados: {dupes}")
        if self.DEFAULT_TEMPLATE_ID.value not in ids:
            raise ValueError(
                f"DEFAULT_TEMPLATE_ID '{self.DEFAULT_TEMPLATE_ID.value}' não está em TEMPLATES_DISPONIVEIS"
            )
        return self


# --- Instanciação Global ---
settings = AppSettings()