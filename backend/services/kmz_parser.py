import zipfile
import os
import re
import xml.etree.ElementTree as ET
from statistics import mean
from shapely.geometry import Polygon, Point
from math import sqrt
import uuid

# --- Funções Auxiliares ---

def normalizar_nome(nome: str) -> str:
    """Remove caracteres especiais, espaços extras e converte para minúsculas."""
    if not nome:
        return ""
    nome = nome.lower()
    nome = re.sub(r'[^a-z0-9À-ú ]', '', nome)  # Mantém letras acentuadas e espaços
    nome = re.sub(r'\s+', ' ', nome).strip()  # Remove espaços extras
    return nome


# --- Função Principal ---

def parse_kmz(caminho_kmz: str, pasta_extracao: str) -> tuple:
    antena = None
    pivos_de_pontos = []
    ciclos = []
    bombas = []

    print(f"⚙️ Processando KMZ: {caminho_kmz}")

    try:
        with zipfile.ZipFile(caminho_kmz, 'r') as kmz:
            kml_file_name = next((f for f in kmz.namelist() if f.lower().endswith('.kml')), None)

            if not kml_file_name:
                raise ValueError("Nenhum arquivo .kml encontrado dentro do KMZ.")

            kmz.extract(kml_file_name, pasta_extracao)
            caminho_kml_completo = os.path.join(pasta_extracao, kml_file_name)
            print(f"   -> Extraído KML: {caminho_kml_completo}")

            tree = ET.parse(caminho_kml_completo)
            root = tree.getroot()
            ns = {"kml": "http://www.opengis.net/kml/2.2"}

            for placemark in root.findall(".//kml:Placemark", ns):
                nome_tag = placemark.find("kml:name", ns)
                ponto_tag = placemark.find(".//kml:Point/kml:coordinates", ns)
                linha_tag = placemark.find(".//kml:LineString/kml:coordinates", ns)

                nome_texto_original = nome_tag.text.strip() if nome_tag is not None and nome_tag.text else ""
                nome_lower = nome_texto_original.lower()

                if ponto_tag is not None and ponto_tag.text:
                    coords = ponto_tag.text.strip().split(",")
                    if len(coords) < 2: continue
                    lon, lat = float(coords[0]), float(coords[1])

                    if any(p_key in nome_lower for p_key in ["antena", "torre", "barracão", "galpão", "silo", "caixa", "repetidora"]):
                        match = re.search(r"(\d{1,3})\s*(m|metros)", nome_lower)
                        altura = int(match.group(1)) if match else 15
                        antena = {"lat": lat, "lon": lon, "altura": altura, "altura_receiver": 3, "nome": nome_texto_original}
                        print(f"   -> Antena encontrada: {nome_texto_original} ({lat:.6f}, {lon:.6f}) Alt: {altura}m")
                    elif "pivô" in nome_lower or "pivo" in nome_lower or re.match(r"p\s?\d+", nome_lower):
                        pivos_de_pontos.append({"nome": nome_texto_original, "lat": lat, "lon": lon})
                        print(f"   -> Pivô (Ponto) encontrado: {nome_texto_original} ({lat:.6f}, {lon:.6f})")
                    elif "bomba" in nome_lower or "irripump" in nome_lower:
                        bombas.append({"nome": nome_texto_original, "lat": lat, "lon": lon})
                        print(f"   -> Bomba encontrada: {nome_texto_original} ({lat:.6f}, {lon:.6f})")

                elif linha_tag is not None and linha_tag.text and "medida do círculo" in nome_lower:
                    coords_texto_lista = linha_tag.text.strip().split()
                    coords_para_ciclo = []
                    for c_str in coords_texto_lista:
                        partes = c_str.split(",")
                        if len(partes) >= 2:
                            coords_para_ciclo.append([float(partes[1]), float(partes[0])])  # [lat, lon]
                    if coords_para_ciclo:
                        ciclos.append({"nome_original_circulo": nome_texto_original, "coordenadas": coords_para_ciclo})
                        print(f"   -> Círculo encontrado: {nome_texto_original}")

            if os.path.exists(caminho_kml_completo):
                os.remove(caminho_kml_completo)

    except Exception as e:
        print(f"❌ Erro ao processar KMZ: {e}")
        raise

    # --- Consolidação dos Pivôs ---

    final_pivos_list = list(pivos_de_pontos)
    todos_nomes_pivos_finais_normalizados = {normalizar_nome(p["nome"]) for p in final_pivos_list}

    pivos_pontos_geom = [Point(p['lon'], p['lat']) for p in pivos_de_pontos]
    virtual_pivot_counter = 1

    for ciclo_data in ciclos:
        nome_circulo = ciclo_data["nome_original_circulo"]
        coordenadas_ciclo = ciclo_data["coordenadas"]

        try:
            poligono_ciclo = Polygon([(lon, lat) for lat, lon in coordenadas_ciclo])
        except Exception as e:
            print(f"   -> ⚠️ Erro criando polígono do círculo '{nome_circulo}': {e}")
            poligono_ciclo = None

        tem_pivo_dentro = False
        if poligono_ciclo and poligono_ciclo.is_valid:
            for ponto_pivo in pivos_pontos_geom:
                if poligono_ciclo.contains(ponto_pivo):
                    print(f"   -> 🔍 Círculo '{nome_circulo}' já possui pivô dentro. Pulando criação.")
                    tem_pivo_dentro = True
                    break

        if tem_pivo_dentro:
            continue

        # Cálculo do centro
        centro_lat, centro_lon = 0.0, 0.0
        try:
            coords_lonlat = [(lon, lat) for lat, lon in coordenadas_ciclo]
            if len(coords_lonlat) >= 3 and Polygon(coords_lonlat).is_valid:
                poligono = Polygon(coords_lonlat)
                centroide = poligono.centroid
                centro_lat, centro_lon = centroide.y, centroide.x
            else:
                centro_lat = mean([lat for lat, lon in coordenadas_ciclo])
                centro_lon = mean([lon for lat, lon in coordenadas_ciclo])
        except Exception as e:
            print(f"   -> ⚠️ Erro no cálculo do centroide para '{nome_circulo}': {e}")
            if not coordenadas_ciclo: continue
            centro_lat = mean([lat for lat, lon in coordenadas_ciclo])
            centro_lon = mean([lon for lat, lon in coordenadas_ciclo])

        # Definindo nome do pivô virtual
        nome_final_para_virtual = f"Pivô {virtual_pivot_counter}"
        while normalizar_nome(nome_final_para_virtual) in todos_nomes_pivos_finais_normalizados:
            virtual_pivot_counter += 1
            nome_final_para_virtual = f"Pivô {virtual_pivot_counter}"

        final_pivos_list.append({"nome": nome_final_para_virtual, "lat": centro_lat, "lon": centro_lon})
        todos_nomes_pivos_finais_normalizados.add(normalizar_nome(nome_final_para_virtual))
        print(f"   -> Pivô virtual criado: '{nome_final_para_virtual}' ({centro_lat:.6f}, {centro_lon:.6f})")

        virtual_pivot_counter += 1

    if not antena:
        print("   -> ⚠️ Nenhuma antena encontrada no KMZ.")

    print(f"   -> ✅ Processamento KMZ concluído: {len(final_pivos_list)} pivôs totais, {len(bombas)} bombas.")
    return antena, final_pivos_list, ciclos, bombas
