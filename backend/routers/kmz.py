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

# Usa a variável de caminho absoluto do config.py
INPUT_KMZ_PATH = os.path.join(config.ARQUIVOS_DIR_PATH, "entrada.kmz")

@router.post("/processar")
async def processar_kmz_endpoint(file: UploadFile = File(...)):
    """
    Recebe um arquivo KMZ, salva, processa e retorna os dados extraídos.
    """
    try:
        print("📥 Recebendo arquivo KMZ...")
        conteudo = await file.read()

        # Garante que o diretório de arquivos exista (config.py já faz isso, mas é uma segurança extra)
        os.makedirs(config.ARQUIVOS_DIR_PATH, exist_ok=True)
        with open(INPUT_KMZ_PATH, "wb") as f:
            f.write(conteudo)
        print(f"   -> KMZ salvo em: {INPUT_KMZ_PATH}")

        # Chama o parser, passando o caminho absoluto para extração se necessário (embora config.py já crie)
        antena, pivos, ciclos, bombas = kmz_parser.parse_kmz(INPUT_KMZ_PATH, config.ARQUIVOS_DIR_PATH)

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
        print(f"❌ Erro Interno em /kmz/processar: {e}")
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

    # Usa os caminhos absolutos do config.py
    caminho_imagem_principal = os.path.join(config.IMAGENS_DIR_PATH, imagem)
    caminho_bounds_principal = os.path.join(config.IMAGENS_DIR_PATH, bounds_file)

    if not os.path.exists(caminho_imagem_principal):
        raise HTTPException(status_code=404, detail=f"Imagem principal '{imagem}' não encontrada em {config.IMAGENS_DIR_PATH}.")
    if not os.path.exists(caminho_bounds_principal):
        raise HTTPException(status_code=404, detail=f"Bounds '{bounds_file}' não encontrados em {config.IMAGENS_DIR_PATH}.")

    try:
        antena, pivos, ciclos, _ = kmz_parser.parse_kmz(INPUT_KMZ_PATH, config.ARQUIVOS_DIR_PATH)

        with open(caminho_bounds_principal, "r") as f:
            bounds_principal = json.load(f).get("bounds")

        if not antena or not pivos or not bounds_principal:
             raise HTTPException(status_code=500, detail="Dados incompletos para exportar.")

        kml = simplekml.Kml(name="Estudo de Sinal Irricontrol")
        doc = kml.document

        torre_style = simplekml.Style()
        torre_style.iconstyle.icon.href = "cloudrf.png" # Nome do arquivo que estará na raiz do KMZ
        torre_style.iconstyle.scale = 1.2
        # pivo_style = simplekml.Style() # Removido se não estiver sendo usado
        # pivo_style.iconstyle.scale = 0.8

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
        ground_main.icon.href = imagem # Nome do arquivo que estará na raiz do KMZ
        b = bounds_principal
        ground_main.latlonbox.north, ground_main.latlonbox.south = b[2], b[0]
        ground_main.latlonbox.east, ground_main.latlonbox.west = b[3], b[1]
        ground_main.color = "aaffffff" # Adiciona transparência

        arquivos_a_adicionar_ao_kmz = [(caminho_imagem_principal, imagem)] # (caminho_no_servidor, nome_no_kmz)

        # Lista arquivos da pasta de imagens no servidor
        for arq_nome_no_servidor in os.listdir(config.IMAGENS_DIR_PATH):
            if arq_nome_no_servidor.startswith("repetidora_") and arq_nome_no_servidor.endswith(".png"):
                caminho_rep_img_servidor = os.path.join(config.IMAGENS_DIR_PATH, arq_nome_no_servidor)
                caminho_rep_json_servidor = caminho_rep_img_servidor.replace(".png", ".json")

                if os.path.exists(caminho_rep_json_servidor):
                    with open(caminho_rep_json_servidor, "r") as f:
                        bounds_rep = json.load(f).get("bounds")

                    if bounds_rep:
                        ground_rep = doc.newgroundoverlay(name=f"Repetidora {arq_nome_no_servidor}")
                        ground_rep.icon.href = arq_nome_no_servidor # Nome do arquivo na raiz do KMZ
                        b_rep = bounds_rep
                        ground_rep.latlonbox.north, ground_rep.latlonbox.south = b_rep[2], b_rep[0]
                        ground_rep.latlonbox.east, ground_rep.latlonbox.west = b_rep[3], b_rep[1]
                        ground_rep.color = "aaffffff" # Adiciona transparência
                        arquivos_a_adicionar_ao_kmz.append((caminho_rep_img_servidor, arq_nome_no_servidor))
                        print(f"      -> Overlay {arq_nome_no_servidor} adicionado ao KML.")

        # Salva o KML temporariamente
        caminho_kml_temp = os.path.join(config.ARQUIVOS_DIR_PATH, "estudo_temp.kml")
        kml.save(caminho_kml_temp)
        print(f"   -> KML temporário salvo em: {caminho_kml_temp}")

        # Cria o arquivo KMZ final
        nome_kmz_final = f"estudo-irricontrol-{datetime.now().strftime('%Y%m%d_%H%M%S')}.kmz"
        caminho_kmz_final = os.path.join(config.ARQUIVOS_DIR_PATH, nome_kmz_final)

        print(f"   -> Criando KMZ final: {caminho_kmz_final}")
        with zipfile.ZipFile(caminho_kmz_final, "w", zipfile.ZIP_DEFLATED) as kmz_zip:
            kmz_zip.write(caminho_kml_temp, "doc.kml") # KML principal deve ter este nome dentro do ZIP

            # Adiciona o ícone da torre (copiado da pasta de imagens do servidor para a raiz do KMZ)
            caminho_icone_servidor = os.path.join(config.IMAGENS_DIR_PATH, "cloudrf.png")
            if os.path.exists(caminho_icone_servidor):
                kmz_zip.write(caminho_icone_servidor, "cloudrf.png") # Nome do arquivo na raiz do KMZ

            # Adiciona todas as imagens de overlay (principal e repetidoras) à raiz do KMZ
            for caminho_origem_servidor, nome_destino_no_kmz in arquivos_a_adicionar_ao_kmz:
                if os.path.exists(caminho_origem_servidor):
                    kmz_zip.write(caminho_origem_servidor, nome_destino_no_kmz)
        
        os.remove(caminho_kml_temp) # Limpa o KML temporário

        print("   -> Exportação KMZ concluída.")
        return FileResponse(
            caminho_kmz_final,
            media_type="application/vnd.google-earth.kmz",
            filename=nome_kmz_final
        )

    except Exception as e:
        print(f"❌ Erro Interno em /kmz/exportar: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao exportar KMZ: {str(e)}")


@router.get("/icone-torre")
async def get_icone_torre():
    """Serve a imagem do ícone da torre."""
    # Usa o caminho absoluto do config.py
    caminho_icone = os.path.join(config.IMAGENS_DIR_PATH, "cloudrf.png")
    if os.path.exists(caminho_icone):
        return FileResponse(caminho_icone, media_type="image/png")
    raise HTTPException(status_code=404, detail="Ícone não encontrado.")