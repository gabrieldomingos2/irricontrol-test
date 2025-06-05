# backend/config.py

import os
from pathlib import Path
from typing import List, Optional, Dict, Any

from pydantic import Field, HttpUrl, BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


# --- Modelos Pydantic para estruturas aninhadas nos templates ---
class TransmitterSettings(BaseModel):
    txw: float
    bwi: float

class ReceiverSettings(BaseModel):
    lat: float = 0.0
    lon: float = 0.0
    alt: int = 3
    rxg: float
    rxs: int

class AntennaSettings(BaseModel):
    txg: float
    fbr: float

class TemplateSettings(BaseModel):
    id: str
    nome: str
    frq: int
    col: str
    site: str
    rxs: int
    transmitter: TransmitterSettings
    receiver: ReceiverSettings
    antenna: AntennaSettings

# --- Classe Principal de Configurações ---
class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    APP_NAME: str = "Irricontrol Signal Simulator API"
    APP_VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    ALLOWED_ORIGINS_CSV: str = Field(default="http://localhost,http://localhost:8080,http://127.0.0.1,http://127.0.0.1:8080,null,http://localhost:5173", validation_alias="ALLOWED_ORIGINS_CSV")
    NETLIFY_APP_URL: Optional[str] = Field(None, validation_alias="NETLIFY_APP_URL")
    BACKEND_PUBLIC_URL: Optional[HttpUrl] = Field(None, validation_alias="BACKEND_PUBLIC_URL")

    @property
    def ALLOWED_ORIGINS(self) -> List[str]:
        origins_from_csv = [origin.strip() for origin in self.ALLOWED_ORIGINS_CSV.split(',')]
        if self.NETLIFY_APP_URL:
            normalized_netlify_url = self.NETLIFY_APP_URL.strip().rstrip('/')
            if normalized_netlify_url not in origins_from_csv:
                origins_from_csv.append(normalized_netlify_url)
        return [origin for origin in origins_from_csv if origin]

    BACKEND_DIR: Path = Path(__file__).resolve().parent
    PROJECT_ROOT_DIR: Path = BACKEND_DIR.parent
    STATIC_DIR_NAME: str = "static"
    IMAGENS_DIR_NAME: str = "imagens"
    ARQUIVOS_DIR_NAME: str = "arquivos"

    @property
    def STATIC_DIR_PATH(self) -> Path:
        return self.BACKEND_DIR / self.STATIC_DIR_NAME

    @property
    def IMAGENS_DIR_PATH(self) -> Path:
        return self.STATIC_DIR_PATH / self.IMAGENS_DIR_NAME

    @property
    def ARQUIVOS_DIR_PATH(self) -> Path:
        return self.BACKEND_DIR / self.ARQUIVOS_DIR_NAME

    CLOUDRF_API_KEY: Optional[str] = Field(None, validation_alias="CLOUDRF_API_KEY")
    CLOUDRF_API_URL: HttpUrl = Field(default="https://api.cloudrf.com/area", validation_alias="CLOUDRF_API_URL")
    HTTP_TIMEOUT: float = Field(default=60.0, validation_alias="HTTP_TIMEOUT")
    LOG_LEVEL: str = "INFO"

    TEMPLATES_DISPONIVEIS: List[TemplateSettings] = [
        {
            "id": "Brazil_V6", "nome": "🇧🇷 Brazil V6", "frq": 915,
            "col": "IRRICONTRO.dBm", "site": "Brazil_V6", "rxs": -90,
            "transmitter": {"txw": 0.3, "bwi": 0.1},
            "receiver": {"lat": 0, "lon": 0, "alt": 3, "rxg": 3, "rxs": -90},
            "antenna": {"txg": 3, "fbr": 3}
        },
        {
            "id": "Europe_V6_XR", "nome": "🇪🇺 Europe V6 XR", "frq": 868,
            "col": "IRRIEUROPE.dBm", "site": "V6_XR.dBm", "rxs": -105,
            "transmitter": {"txw": 0.02, "bwi": 0.05},
            "receiver": {"lat": 0, "lon": 0, "alt": 3, "rxg": 2.1, "rxs": -105},
            "antenna": {"txg": 2.1, "fbr": 2.1}
        }
    ]

    def initialize_directories(self) -> None:
        print(f"INFO: Verificando/Criando diretório de imagens em: {self.IMAGENS_DIR_PATH}")
        self.IMAGENS_DIR_PATH.mkdir(parents=True, exist_ok=True)
        print(f"INFO: Verificando/Criando diretório de arquivos em: {self.ARQUIVOS_DIR_PATH}")
        self.ARQUIVOS_DIR_PATH.mkdir(parents=True, exist_ok=True)
        if not self.CLOUDRF_API_KEY:
            print("⚠️ ALERTA DE SEGURANÇA: CLOUDRF_API_KEY não está definida!")
        if not self.BACKEND_PUBLIC_URL:
            print("⚠️ ALERTA DE CONFIGURAÇÃO: BACKEND_PUBLIC_URL não está definida! As URLs de imagem podem estar incorretas.")

    def obter_template(self, template_id: str) -> TemplateSettings:
        # Agora self.TEMPLATES_DISPONIVEIS contém objetos TemplateSettings
        # Não é mais necessário TemplateSettings(**t_obj) dentro do next
        template_obj = next(
            (t_obj for t_obj in self.TEMPLATES_DISPONIVEIS if t_obj.id == template_id), # Acesso por atributo t_obj.id
            None
        )
        if not template_obj:
            # Acessa o primeiro template (que já é um objeto TemplateSettings) e seu id
            print(f"⚠️ Template '{template_id}' não encontrado. Usando padrão '{self.TEMPLATES_DISPONIVEIS[0].id}'.")
            return self.TEMPLATES_DISPONIVEIS[0] # Retorna o objeto diretamente
        return template_obj

    def listar_templates_ids(self) -> List[str]:
        # Agora self.TEMPLATES_DISPONIVEIS contém objetos TemplateSettings
        return [t_obj.id for t_obj in self.TEMPLATES_DISPONIVEIS] # Acesso por atributo t_obj.id

settings = AppSettings()
