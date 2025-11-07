#models.py

from pydantic import BaseModel, Field


class TransmitterSettings(BaseModel):
    """Configuração do transmissor."""
    model_config = {"frozen": True}

    txw: float = Field(gt=0, description="Potência de transmissão em Watts (>0)")
    bwi: float = Field(ge=0, description="Largura de banda (>=0)")


class ReceiverSettings(BaseModel):
    """Configuração do receptor."""
    model_config = {"frozen": True}

    lat: float = Field(default=0.0, ge=-90, le=90)
    lon: float = Field(default=0.0, ge=-180, le=180)
    alt: int = Field(default=3, ge=0)
    rxg: float = Field(gt=0)
    rxs: int = Field(le=0, description="Sensibilidade (dBm) deve ser <= 0")


class AntennaSettings(BaseModel):
    """Configuração da antena."""
    model_config = {"frozen": True}

    txg: float = Field(ge=0)
    fbr: float = Field(ge=0)


class TemplateSettings(BaseModel):
    """Template completo de simulação (transmissor, receptor e antena)."""
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