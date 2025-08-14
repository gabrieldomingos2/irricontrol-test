# backend/services/farm_service.py
import logging
import json
import requests
import cv2
import numpy as np
from pathlib import Path
from typing import List, Tuple

from backend.config import settings

logger = logging.getLogger("irricontrol")

def get_satellite_image_placeholder(job_id: str, aoi: List[Tuple[float, float]]) -> Tuple[Path, List[float]]:
    """
    FUNÇÃO PLACEHOLDER: No mundo real, esta função se conectaria a uma API como
    Sentinel Hub ou Google Earth Engine para baixar a imagem da área (AOI).
    Para este exemplo, usaremos uma imagem de amostra.
    """
    logger.warning("Usando imagem de satélite de amostra (placeholder). Substitua pela integração real.")

    # Lógica real:
    # 1. Calcular o Bounding Box (caixa delimitadora) a partir da AOI.
    # 2. Montar a requisição para a API de satélite com esse Bounding Box.
    # 3. Baixar a imagem.
    # 4. Retornar o caminho da imagem e o Bounding Box geográfico [min_lon, min_lat, max_lon, max_lat].

    # Para a PoC, vamos simular isso:
    image_path = settings.STATIC_DIR_PATH / "sample_satellite.jpg" # Você precisa adicionar uma imagem de teste aqui
    if not image_path.exists():
        raise FileNotFoundError("Imagem de amostra 'sample_satellite.jpg' não encontrada em /static.")

    # Bounding Box Fixo para a imagem de amostra (AJUSTE CONFORME SUA IMAGEM)
    # Exemplo para uma área no Mato Grosso
    bounding_box = [-56.2, -14.8, -56.0, -14.6] 
    return image_path, bounding_box


def detect_pivots_with_opencv(image_path: Path) -> List[Tuple[int, int, int]]:
    """Usa OpenCV para detectar círculos (pivôs) em uma imagem."""
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        logger.error(f"Não foi possível carregar a imagem de {image_path}")
        return []

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (9, 9), 2)

    # Parâmetros da detecção de Hough - podem precisar de ajuste
    circles = cv2.HoughCircles(
        blurred,
        cv2.HOUGH_GRADIENT,
        dp=1.2,          # Inverso da resolução do acumulador
        minDist=100,     # Distância mínima entre centros de círculos
        param1=50,       # Limiar superior para o detector de bordas Canny
        param2=30,       # Limiar do acumulador para detecção de centros
        minRadius=20,    # Raio mínimo do círculo em pixels
        maxRadius=200    # Raio máximo do círculo em pixels
    )

    detected_pivots = []
    if circles is not None:
        circles = np.round(circles[0, :]).astype("int")
        for (x, y, r) in circles:
            detected_pivots.append((x, y, r))
    logger.info(f"OpenCV detectou {len(detected_pivots)} pivôs.")
    return detected_pivots


def pixel_to_geo(pivots_pixels: List, img_width: int, img_height: int, bbox_geo: List):
    """Converte as coordenadas de pivôs de pixels para geográficas."""
    geo_pivots = []
    min_lon, min_lat, max_lon, max_lat = bbox_geo
    lon_range = max_lon - min_lon
    lat_range = max_lat - min_lat

    for (x, y, r_px) in pivots_pixels:
        lon = min_lon + (x / img_width) * lon_range
        lat = max_lat - (y / img_height) * lat_range # Eixo Y é invertido

        # Estima o raio em metros (aproximação)
        lon_per_px = lon_range / img_width
        radius_deg = r_px * lon_per_px
        radius_m = radius_deg * 111320 * np.cos(np.radians(lat))

        geo_pivots.append({"lat": lat, "lon": lon, "raio": radius_m})
    return geo_pivots


async def detect_pivots_in_background(job_id: str, aoi: List[Tuple[float, float]]):
    result_file_path = settings.ARQUIVOS_DIR_PATH / job_id / "detection_result.json"
    with open(result_file_path, "w") as f:
        json.dump({"status": "processing"}, f)

    try:
        # 1. Obter imagem de satélite
        image_path, bbox_geo = get_satellite_image_placeholder(job_id, aoi)

        # 2. Detectar pivôs na imagem (pixels)
        pivots_in_pixels = detect_pivots_with_opencv(image_path)

        # 3. Converter coordenadas de pixels para Geo
        img = cv2.imread(str(image_path))
        h, w, _ = img.shape
        pivots_in_geo = pixel_to_geo(pivots_in_pixels, w, h, bbox_geo)

        # 4. Formatar para o frontend
        pivos_finais = []
        for i, p in enumerate(pivots_in_geo):
            pivos_finais.append({
                "nome": f"Pivô Detectado {i+1}",
                "lat": p["lat"],
                "lon": p["lon"],
                "type": "pivo",
                "raio": p["raio"]
            })

        final_result = {"status": "complete", "data": {"pivos": pivos_finais}}
        with open(result_file_path, "w") as f:
            json.dump(final_result, f)
        logger.info(f"BG_TASK (Farm): Detecção para job {job_id} concluída.")

    except Exception as e:
        logger.error(f"BG_TASK (Farm): Falha na detecção para job {job_id}: {e}", exc_info=True)
        error_result = {"status": "failed", "error": str(e)}
        with open(result_file_path, "w") as f:
            json.dump(error_result, f)