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

# Define o nome do ícone da torre (embutido)
TORRE_ICON_NAME = "cloudrf.png"
# Define a URL do ícone padrão para pivôs e bombas
DEFAULT_ICON_URL = "http://maps.google.com/mapfiles/kml/pushpin/ylw-pushpin.png"


@router.post("/processar")
async def processar_kmz_endpoint(file: UploadFile = File(...)):
    """
    Recebe um arquivo KMZ, salva, processa e retorna os dados extraídos.
    """
    try:
        print("📥 Recebendo arquivo KMZ...")
        conteudo = await file.read()

        # Garante que o diretório de arquivos exista
        os.makedirs(config.ARQUIVOS_DIR_PATH, exist_ok=True)
        with open(INPUT_KMZ_PATH, "wb") as f:
            f.write(conteudo)
        print(f"   -> KMZ salvo em: {INPUT_KMZ_PATH}")

        # Chama o parser
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

    caminho_imagem_principal = os.path.join(config.IMAGENS_DIR_PATH, imagem)
    caminho_bounds_principal = os.path.join(config.IMAGENS_DIR_PATH, bounds_file)

    if not os.path.exists(caminho_imagem_principal):
        raise HTTPException(status_code=404, detail=f"Imagem principal '{imagem}' não encontrada em {config.IMAGENS_DIR_PATH}.")
    if not os.path.exists(caminho_bounds_principal):
        raise HTTPException(status_code=404, detail=f"Bounds '{bounds_file}' não encontrados em {config.IMAGENS_DIR_PATH}.")

    try:
        antena, pivos, ciclos, bombas = kmz_parser.parse_kmz(INPUT_KMZ_PATH, config.ARQUIVOS_DIR_PATH)

        with open(caminho_bounds_principal, "r") as f:
            bounds_principal = json.load(f).get("bounds")

        if not antena or not pivos or not ciclos or (bombas is None) or not bounds_principal:
             print("⚠️ Dados incompletos para exportar. Verifique antena, pivos, ciclos, bombas e bounds.")
             raise HTTPException(status_code=500, detail="Dados incompletos (antena, pivos, ciclos ou bombas) para exportar.")

        kml = simplekml.Kml(name="Estudo de Sinal Irricontrol")
        doc = kml.document

        # --- ESTILOS ---
        torre_style = simplekml.Style()
        torre_style.iconstyle.icon.href = TORRE_ICON_NAME
        torre_style.iconstyle.scale = 1.2
        torre_style.labelstyle.scale = 1.1

        default_point_style = simplekml.Style()
        default_point_style.iconstyle.icon.href = DEFAULT_ICON_URL
        default_point_style.iconstyle.scale = 1.0
        default_point_style.labelstyle.scale = 1.0

        repetidora_style = simplekml.Style()
        repetidora_style.iconstyle.icon.href = TORRE_ICON_NAME
        repetidora_style.iconstyle.scale = 1.1
        repetidora_style.labelstyle.scale = 1.0

        print("   -> Adicionando elementos ao KML em pastas...")

        # --- PASTA TORRE PRINCIPAL ---
        antena_nome = antena.get("nome", "Antena Principal")
        folder_torre = doc.newfolder(name=antena_nome) # Cria pasta para a torre

        pnt_antena = folder_torre.newpoint(name=antena_nome, coords=[(antena["lon"], antena["lat"])]) # Ponto dentro da pasta
        pnt_antena.description = f"Altura: {antena.get('altura', 'N/A')}m"
        pnt_antena.style = torre_style

        ground_main = folder_torre.newgroundoverlay(name="Cobertura Principal") # Overlay dentro da pasta
        ground_main.icon.href = imagem
        b = bounds_principal
        ground_main.latlonbox.north, ground_main.latlonbox.south = b[2], b[0]
        ground_main.latlonbox.east, ground_main.latlonbox.west = b[3], b[1]
        ground_main.color = "ffffffff"
        print(f"   -> Pasta '{antena_nome}' criada.")

        # --- PASTA PIVÔS ---
        folder_pivos = doc.newfolder(name="Pivôs")
        for i, p in enumerate(pivos):
            pivo_nome = p.get("nome", f"Pivo {i+1}")
            pnt_pivo = folder_pivos.newpoint(name=pivo_nome, coords=[(p["lon"], p["lat"])])
            pnt_pivo.style = default_point_style
        print("   -> Pasta 'Pivôs' criada.")

        # --- PASTA CICLOS ---
        folder_ciclos = doc.newfolder(name="Ciclos")
        for i, ciclo in enumerate(ciclos):
            ciclo_nome = ciclo.get("nome", f"Ciclo {i+1}")
            pol = folder_ciclos.newpolygon(name=ciclo_nome)
            pol.outerboundaryis = [(lon, lat) for lat, lon in ciclo["coordenadas"]]
            pol.style.polystyle.fill = 0
            pol.style.linestyle.color = simplekml.Color.red
            pol.style.linestyle.width = 4
        print("   -> Pasta 'Ciclos' criada.")

        # --- PASTA BOMBAS ---
        if bombas:
            folder_bombas = doc.newfolder(name="Bombas")
            print("   -> Adicionando bombas e irripumps...")
            for i, bomba in enumerate(bombas):
                bomba_nome = bomba.get("nome", f"Bomba {i+1}")
                pnt_bomba = folder_bombas.newpoint(name=bomba_nome, coords=[(bomba["lon"], bomba["lat"])])
                pnt_bomba.style = default_point_style
            print("   -> Pasta 'Bombas' criada.")

        arquivos_a_adicionar_ao_kmz = [(caminho_imagem_principal, imagem)]

        # --- PASTAS REPETIDORAS ---
        print("   -> Adicionando repetidoras em pastas individuais...")
        for arq_nome_no_servidor in os.listdir(config.IMAGENS_DIR_PATH):
            if arq_nome_no_servidor.startswith("repetidora_") and arq_nome_no_servidor.endswith(".png"):
                caminho_rep_img_servidor = os.path.join(config.IMAGENS_DIR_PATH, arq_nome_no_servidor)
                caminho_rep_json_servidor = caminho_rep_img_servidor.replace(".png", ".json")

                if os.path.exists(caminho_rep_json_servidor):
                    with open(caminho_rep_json_servidor, "r") as f:
                        bounds_rep = json.load(f).get("bounds")

                    if bounds_rep:
                        rep_point_name = arq_nome_no_servidor.replace('.png', '').replace('_', ' ').capitalize()
                        
                        folder_rep = doc.newfolder(name=rep_point_name) # Cria pasta para a repetidora

                        # Adiciona Overlay DENTRO da pasta
                        ground_rep = folder_rep.newgroundoverlay(name=f"Cobertura {rep_point_name}")
                        ground_rep.icon.href = arq_nome_no_servidor
                        b_rep = bounds_rep
                        ground_rep.latlonbox.north, ground_rep.latlonbox.south = b_rep[2], b_rep[0]
                        ground_rep.latlonbox.east, ground_rep.latlonbox.west = b_rep[3], b_rep[1]
                        ground_rep.color = "ffffffff"
                        arquivos_a_adicionar_ao_kmz.append((caminho_rep_img_servidor, arq_nome_no_servidor))

                        # Adiciona Ponto DENTRO da pasta
                        center_lat = (b_rep[0] + b_rep[2]) / 2
                        center_lon = (b_rep[1] + b_rep[3]) / 2
                        pnt_rep = folder_rep.newpoint(name=rep_point_name, coords=[(center_lon, center_lat)])
                        pnt_rep.style = repetidora_style
                        print(f"      -> Pasta '{rep_point_name}' (ponto e overlay) adicionada.")


        caminho_kml_temp = os.path.join(config.ARQUIVOS_DIR_PATH, "estudo_temp.kml")
        kml.save(caminho_kml_temp)
        print(f"   -> KML temporário salvo em: {caminho_kml_temp}")

        nome_kmz_final = f"estudo-irricontrol-{datetime.now().strftime('%Y%m%d_%H%M%S')}.kmz"
        caminho_kmz_final = os.path.join(config.ARQUIVOS_DIR_PATH, nome_kmz_final)

        print(f"   -> Criando KMZ final: {caminho_kmz_final}")
        with zipfile.ZipFile(caminho_kmz_final, "w", zipfile.ZIP_DEFLATED) as kmz_zip:
            kmz_zip.write(caminho_kml_temp, "doc.kml")

            caminho_icone_torre = os.path.join(config.IMAGENS_DIR_PATH, TORRE_ICON_NAME)
            if os.path.exists(caminho_icone_torre):
                kmz_zip.write(caminho_icone_torre, TORRE_ICON_NAME)
                print(f"      -> Ícone '{TORRE_ICON_NAME}' adicionado ao KMZ.")
            else:
                print(f"      -> ⚠️ ATENÇÃO: Ícone '{TORRE_ICON_NAME}' não encontrado.")

            for caminho_origem_servidor, nome_destino_no_kmz in arquivos_a_adicionar_ao_kmz:
                if os.path.exists(caminho_origem_servidor):
                    kmz_zip.write(caminho_origem_servidor, nome_destino_no_kmz)

        os.remove(caminho_kml_temp)

        print("   -> Exportação KMZ concluída.")
        return FileResponse(
            caminho_kmz_final,
            media_type="application/vnd.google-earth.kmz",
            filename=nome_kmz_final
        )

    except Exception as e:
        print(f"❌ Erro Interno em /kmz/exportar: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao exportar KMZ: {type(e).__name__} - {str(e)}")


@router.get("/icone-torre")
async def get_icone_torre():
    """Serve a imagem do ícone da torre."""
    caminho_icone = os.path.join(config.IMAGENS_DIR_PATH, TORRE_ICON_NAME)
    if os.path.exists(caminho_icone):
        return FileResponse(caminho_icone, media_type="image/png")
    raise HTTPException(status_code=404, detail="Ícone não encontrado.")