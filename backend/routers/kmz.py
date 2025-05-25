from fastapi import APIRouter, UploadFile, File, Query, HTTPException
from fastapi.responses import FileResponse
import os
import zipfile
import json
import simplekml
from datetime import datetime

# Usa imports absolutos
from backend.services import kmz_parser
from backend import config

router = APIRouter(
    prefix="/kmz",
    tags=["KMZ Operations"],
)

INPUT_KMZ_PATH = os.path.join(config.ARQUIVOS_DIR, "entrada.kmz")

@router.post("/processar")
async def processar_kmz_endpoint(file: UploadFile = File(...)):
    """
    Recebe um arquivo KMZ, salva, processa e retorna os dados extraídos.
    """
    try:
        print("📥 Recebendo arquivo KMZ...")
        conteudo = await file.read()

        with open(INPUT_KMZ_PATH, "wb") as f:
            f.write(conteudo)
        print(f"   -> KMZ salvo em: {INPUT_KMZ_PATH}")

        # Chama o parser com o caminho completo
        antena, pivos, ciclos, bombas = kmz_parser.parse_kmz(INPUT_KMZ_PATH, config.ARQUIVOS_DIR)

        if not antena:
             raise HTTPException(status_code=404, detail="Antena principal (torre, barracão, etc.) não encontrada no KMZ.")

        return {
            "antena": antena,
            "pivos": pivos,
            "ciclos": ciclos,
            "bombas": bombas
        }

    except ValueError as ve:
        print(f"❌ Erro de Validação KMZ: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        print(f"❌ Erro Interno em /processar_kmz: {e}")
        raise HTTPException(status_code=500, detail=f"Erro interno ao processar KMZ: {str(e)}")


@router.get("/exportar")
def exportar_kmz_endpoint(
    imagem: str = Query(..., description="Nome da imagem PNG principal."),
    bounds_file: str = Query(..., description="Nome do JSON de bounds principal.")
):
    """
    Gera e retorna um novo arquivo KMZ contendo os dados originais
    e todos os overlays de sinal gerados (principal e repetidoras).
    """
    print("📦 Iniciando exportação KMZ...")

    if not os.path.exists(INPUT_KMZ_PATH):
         raise HTTPException(status_code=400, detail="Nenhum KMZ foi processado ainda. Faça o upload primeiro.")

    # Constrói caminhos absolutos para verificar existência
    caminho_imagem_principal = os.path.join(config.IMAGENS_DIR, imagem)
    caminho_bounds_principal = os.path.join(config.IMAGENS_DIR, bounds_file)

    if not os.path.exists(caminho_imagem_principal):
        raise HTTPException(status_code=404, detail=f"Imagem principal '{imagem}' não encontrada em {config.IMAGENS_DIR}.")
    if not os.path.exists(caminho_bounds_principal):
        raise HTTPException(status_code=404, detail=f"Bounds '{bounds_file}' não encontrados em {config.IMAGENS_DIR}.")

    try:
        antena, pivos, ciclos, bombas = kmz_parser.parse_kmz(INPUT_KMZ_PATH, config.ARQUIVOS_DIR)

        with open(caminho_bounds_principal, "r") as f:
            bounds_principal = json.load(f).get("bounds")

        if not antena or not pivos or not bounds_principal:
             raise HTTPException(status_code=500, detail="Dados incompletos para exportar.")

        kml = simplekml.Kml(name="Estudo de Sinal Irricontrol")
        doc = kml.document

        torre_style = simplekml.Style()
        torre_style.iconstyle.icon.href = "cloudrf.png"
        torre_style.iconstyle.scale = 1.2
        pivo_style = simplekml.Style()
        pivo_style.iconstyle.scale = 0.8

        print("   -> Adicionando elementos ao KML...")
        pnt_antena = doc.newpoint(name=antena["nome"], coords=[(antena["lon"], antena["lat"])])
        pnt_antena.description = f"Altura: {antena['altura']}m"
        pnt_antena.style = torre_style

        for p in pivos:
            doc.newpoint(name=p["nome"], coords=[(p["lon"], p["lat"])])

        for ciclo in ciclos:
            pol = doc.newpolygon(name=ciclo["nome"])
            pol.outerboundaryis = [(lon, lat) for lat, lon in ciclo["coordenadas"]]
            pol.style.polystyle.fill = 0
            pol.style.linestyle.color = simplekml.Color.red
            pol.style.linestyle.width = 2

        print("   -> Adicionando overlays...")
        ground_main = doc.newgroundoverlay(name="Cobertura Principal")
        ground_main.icon.href = imagem
        b = bounds_principal
        ground_main.latlonbox.north, ground_main.latlonbox.south = b[2], b[0]
        ground_main.latlonbox.east, ground_main.latlonbox.west = b[3], b[1]
        ground_main.color = "aaffffff"

        arquivos_a_adicionar = [(caminho_imagem_principal, imagem)]

        for arq in os.listdir(config.IMAGENS_DIR):
            if arq.startswith("repetidora_") and arq.endswith(".png"):
                caminho_rep_img = os.path.join(config.IMAGENS_DIR, arq)
                caminho_rep_json = caminho_rep_img.replace(".png", ".json")

                if os.path.exists(caminho_rep_json):
                    with open(caminho_rep_json, "r") as f:
                        bounds_rep = json.load(f).get("bounds")

                    if bounds_rep:
                        ground_rep = doc.newgroundoverlay(name=f"Repetidora {arq}")
                        ground_rep.icon.href = arq
                        b_rep = bounds_rep
                        ground_rep.latlonbox.north, ground_rep.latlonbox.south = b_rep[2], b_rep[0]
                        ground_rep.latlonbox.east, ground_rep.latlonbox.west = b_rep[3], b_rep[1]
                        ground_rep.color = "aaffffff"
                        arquivos_a_adicionar.append((caminho_rep_img, arq))
                        print(f"      -> Overlay {arq} adicionado.")

        caminho_kml_temp = os.path.join(config.ARQUIVOS_DIR, "estudo_temp.kml")
        kml.save(caminho_kml_temp)
        print(f"   -> KML temporário salvo em: {caminho_kml_temp}")

        nome_kmz_final = f"estudo-irricontrol-{datetime.now().strftime('%Y%m%d_%H%M%S')}.kmz"
        caminho_kmz_final = os.path.join(config.ARQUIVOS_DIR, nome_kmz_final)

        print(f"   -> Criando KMZ final: {caminho_kmz_final}")
        with zipfile.ZipFile(caminho_kmz_final, "w", zipfile.ZIP_DEFLATED) as kmz_zip:
            kmz_zip.write(caminho_kml_temp, "doc.kml")
            caminho_icone = os.path.join(config.IMAGENS_DIR, "cloudrf.png")
            if os.path.exists(caminho_icone):
                kmz_zip.write(caminho_icone, "cloudrf.png")
            for caminho_origem, nome_destino in arquivos_a_adicionar:
                kmz_zip.write(caminho_origem, nome_destino)
        os.remove(caminho_kml_temp)

        print("   -> Exportação KMZ concluída.")
        return FileResponse(
            caminho_kmz_final,
            media_type="application/vnd.google-earth.kmz",
            filename=nome_kmz_final
        )

    except Exception as e:
        print(f"❌ Erro Interno em /exportar_kmz: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao exportar KMZ: {str(e)}")


@router.get("/icone-torre")
async def get_icone_torre():
    """Serve a imagem do ícone da torre."""
    caminho_icone = os.path.join(config.IMAGENS_DIR, "cloudrf.png")
    if os.path.exists(caminho_icone):
        return FileResponse(caminho_icone, media_type="image/png")
    raise HTTPException(status_code=404, detail="Ícone não encontrado.")