import zipfile
import os
import re
import xml.etree.ElementTree as ET
from statistics import mean
from shapely.geometry import Polygon, Point
from math import sqrt


# 🔧 --- Funções Auxiliares ---

def normalizar_nome(nome: str) -> str:
    if not nome:
        return ""
    nome = nome.lower()
    nome = re.sub(r'[^a-z0-9À-ú ]', '', nome)
    nome = re.sub(r'\s+', ' ', nome).strip()
    return nome


def calcular_meio_reta(p1, p2):
    meio_lat = (p1["lat"] + p2["lat"]) / 2
    meio_lon = (p1["lon"] + p2["lon"]) / 2
    return meio_lat, meio_lon


def ponto_central_da_reta_maior(coords):
    max_dist = 0
    ponta1 = ponta2 = None

    for i in range(len(coords)):
        for j in range(i + 1, len(coords)):
            p1 = coords[i]
            p2 = coords[j]
            dist = sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)
            if dist > max_dist:
                max_dist = dist
                ponta1, ponta2 = p1, p2

    meio_lat = (ponta1[0] + ponta2[0]) / 2
    meio_lon = (ponta1[1] + ponta2[1]) / 2
    return meio_lat, meio_lon, ponta1, ponta2


def eh_um_circulo(coords):
    """Detecta se um conjunto de pontos forma um círculo ou curva fechada."""
    if len(coords) < 3:
        return False
    primeiro = Point(coords[0][1], coords[0][0])
    ultimo = Point(coords[-1][1], coords[-1][0])
    distancia = primeiro.distance(ultimo)
    return distancia < 0.0005


# 🚀 --- Função Principal ---

def parse_kmz(caminho_kmz: str, pasta_extracao: str) -> tuple:
    antena = None
    pivos_de_pontos = []
    ciclos = []
    bombas = []
    pontas_retas = {}

    print(f"⚙️ Processando KMZ: {caminho_kmz}")

    try:
        with zipfile.ZipFile(caminho_kmz, 'r') as kmz:
            kml_file_name = next((f for f in kmz.namelist() if f.lower().endswith('.kml')), None)

            if not kml_file_name:
                raise ValueError("Nenhum arquivo .kml encontrado dentro do KMZ.")

            kmz.extract(kml_file_name, pasta_extracao)
            caminho_kml = os.path.join(pasta_extracao, kml_file_name)

            tree = ET.parse(caminho_kml)
            root = tree.getroot()
            ns = {"kml": "http://www.opengis.net/kml/2.2"}

            for placemark in root.findall(".//kml:Placemark", ns):
                nome_tag = placemark.find("kml:name", ns)
                nome_texto_original = nome_tag.text.strip() if nome_tag is not None and nome_tag.text else ""
                nome_lower = nome_texto_original.lower()

                ponto_tag = placemark.find(".//kml:Point/kml:coordinates", ns)
                linha_tag = placemark.find(".//kml:LineString/kml:coordinates", ns)
                poligono_tag = placemark.find(".//kml:Polygon/kml:outerBoundaryIs/kml:LinearRing/kml:coordinates", ns)

                # 🔵 Processa pontos
                if ponto_tag is not None and ponto_tag.text:
                    coords = ponto_tag.text.strip().split(",")
                    if len(coords) < 2:
                        continue
                    lon, lat = float(coords[0]), float(coords[1])

                    if any(p in nome_lower for p in ["central", "antena", "torre", "barracão", "galpão", "silo", "caixa", "repetidora"]):
                        match = re.search(r"(\d{1,3})\s*(m|metros)", nome_lower)
                        altura = int(match.group(1)) if match else 15
                        antena = {
                            "lat": lat, "lon": lon,
                            "altura": altura, "altura_receiver": 3,
                            "nome": nome_texto_original
                        }
                        print(f"   -> Antena encontrada: {nome_texto_original} ({lat:.6f}, {lon:.6f}) Alt: {altura}m")

                    elif "pivô" in nome_lower or "pivo" in nome_lower or re.match(r"p\s?\d+", nome_lower):
                        pivos_de_pontos.append({"nome": nome_texto_original, "lat": lat, "lon": lon})
                        print(f"   -> Pivô (Ponto) encontrado: {nome_texto_original} ({lat:.6f}, {lon:.6f})")

                    elif "bomba" in nome_lower or "irripump" in nome_lower:
                        bombas.append({"nome": nome_texto_original, "lat": lat, "lon": lon})
                        print(f"   -> Bomba encontrada: {nome_texto_original} ({lat:.6f}, {lon:.6f})")

                    elif "ponta 1 reta" in nome_lower or "ponta 2 reta" in nome_lower:
                        key = nome_lower.strip()
                        pontas_retas[key] = {"lat": lat, "lon": lon}
                        print(f"   -> Ponta de reta encontrada: {nome_texto_original} ({lat:.6f}, {lon:.6f})")

                # 🔵 Processa linhas (círculos desenhados como LineString)
                elif linha_tag is not None and linha_tag.text:
                    coords_texto_lista = linha_tag.text.strip().split()
                    coords_para_ciclo = []
                    for c_str in coords_texto_lista:
                        partes = c_str.split(",")
                        if len(partes) >= 2:
                            coords_para_ciclo.append([float(partes[1]), float(partes[0])])

                    if eh_um_circulo(coords_para_ciclo):
                        ciclos.append({
                            "nome_original_circulo": nome_texto_original,
                            "coordenadas": coords_para_ciclo
                        })
                        print(f"   -> 🔵 Círculo detectado pela geometria: {nome_texto_original}")
                    else:
                        print(f"   -> ⚠️ Linha ignorada (não parece círculo): {nome_texto_original}")

                # 🔷 Processa polígonos (Medida do Polígono)
                elif poligono_tag is not None and poligono_tag.text:
                    coords_texto_lista = poligono_tag.text.strip().split()
                    coords_para_poligono = []
                    for c_str in coords_texto_lista:
                        partes = c_str.split(",")
                        if len(partes) >= 2:
                            coords_para_poligono.append([float(partes[1]), float(partes[0])])

                    ciclos.append({
                        "nome_original_circulo": nome_texto_original,
                        "coordenadas": coords_para_poligono
                    })
                    print(f"   -> 🟦 Polígono detectado como ciclo: {nome_texto_original}")

            os.remove(caminho_kml)

    except Exception as e:
        print(f"❌ Erro ao processar KMZ: {e}")
        raise

    # 🔥 Consolidação dos pivôs

    final_pivos_list = list(pivos_de_pontos)
    nomes_pivos = {normalizar_nome(p["nome"]) for p in final_pivos_list}

    pivos_pontos_geom = [Point(p['lon'], p['lat']) for p in pivos_de_pontos]
    contador_virtual = 1

    for ciclo in ciclos:
        nome_circulo = ciclo["nome_original_circulo"]
        coordenadas = ciclo["coordenadas"]

        try:
            poligono = Polygon([(lon, lat) for lat, lon in coordenadas])
        except:
            poligono = None

        tem_pivo_dentro = any(poligono.contains(p) for p in pivos_pontos_geom) if poligono and poligono.is_valid else False

        if tem_pivo_dentro:
            continue

        nome_circulo_lower = nome_circulo.lower()
        ponta1 = pontas_retas.get(f"ponta 1 reta {nome_circulo_lower}") or pontas_retas.get("ponta 1 reta")
        ponta2 = pontas_retas.get(f"ponta 2 reta {nome_circulo_lower}") or pontas_retas.get("ponta 2 reta")

        if ponta1 and ponta2:
            centro_lat, centro_lon = calcular_meio_reta(ponta1, ponta2)
            print(f"   -> 📏 Pivô criado no meio da reta: ({centro_lat:.6f}, {centro_lon:.6f})")
        else:
            try:
                centro_lat, centro_lon, p1, p2 = ponto_central_da_reta_maior(coordenadas)
                print(f"   -> 📐 Pivô criado no centro da reta maior: ({centro_lat:.6f}, {centro_lon:.6f})")
            except Exception as e:
                print(f"   -> ⚠️ Erro no cálculo da reta maior: {e}")
                centro_lat = mean([lat for lat, lon in coordenadas])
                centro_lon = mean([lon for lat, lon in coordenadas])

        nome_virtual = f"Pivô {contador_virtual}"
        while normalizar_nome(nome_virtual) in nomes_pivos:
            contador_virtual += 1
            nome_virtual = f"Pivô {contador_virtual}"

        final_pivos_list.append({"nome": nome_virtual, "lat": centro_lat, "lon": centro_lon})
        nomes_pivos.add(normalizar_nome(nome_virtual))

        print(f"   -> 🛰️ Pivô virtual criado: {nome_virtual} ({centro_lat:.6f}, {centro_lon:.6f})")
        contador_virtual += 1

    print(f"✅ Processamento concluído: {len(final_pivos_list)} pivôs, {len(bombas)} bombas.")
    return antena, final_pivos_list, ciclos, bombas
