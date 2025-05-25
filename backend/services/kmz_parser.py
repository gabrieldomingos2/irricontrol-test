import zipfile
import os
import re
import xml.etree.ElementTree as ET
from statistics import mean
from shapely.geometry import Polygon
from math import sqrt

# --- Funções Auxiliares ---

def normalizar_nome(nome: str) -> str:
    """Remove caracteres especiais e converte para minúsculas."""
    if not nome:
        return ""
    return re.sub(r'[^a-z0-9]', '', nome.lower())

# --- Função Principal de Parsing ---

def parse_kmz(caminho_kmz: str, pasta_extracao: str = "arquivos") -> tuple:
    """
    Processa um arquivo KMZ, extrai o KML e retorna os dados geográficos.

    Args:
        caminho_kmz: Caminho para o arquivo .kmz.
        pasta_extracao: Pasta onde o KML será extraído temporariamente.

    Returns:
        Uma tupla contendo: (antena, pivos, ciclos, bombas).
        antena: Dicionário com dados da antena ou None.
        pivos: Lista de dicionários com dados dos pivôs.
        ciclos: Lista de dicionários com dados dos círculos.
        bombas: Lista de dicionários com dados das bombas.
    """
    antena = None
    pivos = []
    ciclos = []
    bombas = []

    print(f"⚙️ Processando KMZ: {caminho_kmz}")

    try:
        with zipfile.ZipFile(caminho_kmz, 'r') as kmz:
            kml_file = next((f for f in kmz.namelist() if f.lower().endswith('.kml')), None)

            if not kml_file:
                raise ValueError("Nenhum arquivo .kml encontrado dentro do KMZ.")

            # Extrai o KML para a pasta temporária
            kmz.extract(kml_file, pasta_extracao)
            caminho_kml = os.path.join(pasta_extracao, kml_file)
            print(f"   -> Extraído KML: {caminho_kml}")

            tree = ET.parse(caminho_kml)
            root = tree.getroot()
            # Define o namespace KML (importante para encontrar tags)
            ns = {"kml": "http://www.opengis.net/kml/2.2"}

            # Percorre todos os Placemarks no KML
            for placemark in root.findall(".//kml:Placemark", ns):
                nome_tag = placemark.find("kml:name", ns)
                ponto_tag = placemark.find(".//kml:Point/kml:coordinates", ns)
                linha_tag = placemark.find(".//kml:LineString/kml:coordinates", ns)

                nome_texto = nome_tag.text.strip() if nome_tag is not None and nome_tag.text else ""
                nome_lower = nome_texto.lower()

                # Se for um Ponto (Antena, Pivô, Bomba)
                if ponto_tag is not None and ponto_tag.text:
                    coords = ponto_tag.text.strip().split(",")
                    if len(coords) < 2: continue # Ignora se não tiver lon, lat
                    lon, lat = float(coords[0]), float(coords[1])

                    # Identifica Antena/Torre
                    if any(p in nome_lower for p in ["antena", "torre", "barracão", "galpão", "silo", "caixa", "repetidora"]):
                        match = re.search(r"(\d{1,3})\s*(m|metros)", nome_lower)
                        altura = int(match.group(1)) if match else 15 # Padrão 15m
                        antena = {
                            "lat": lat, "lon": lon, "altura": altura,
                            "altura_receiver": 3, "nome": nome_texto # Padrão receiver 3m
                        }
                        print(f"   -> Antena encontrada: {nome_texto} ({lat:.6f}, {lon:.6f}) Alt: {altura}m")

                    # Identifica Pivô
                    elif "pivô" in nome_lower or "pivo" in nome_lower or re.match(r"p\s?\d+", nome_lower):
                         nome_normalizado = normalizar_nome(nome_texto)
                         if not any(normalizar_nome(p["nome"]) == nome_normalizado for p in pivos):
                            pivos.append({"nome": nome_texto, "lat": lat, "lon": lon})
                            print(f"   -> Pivô encontrado: {nome_texto} ({lat:.6f}, {lon:.6f})")

                    # Identifica Bomba
                    elif "bomba" in nome_lower or "irripump" in nome_lower:
                        bombas.append({"nome": nome_texto, "lat": lat, "lon": lon})
                        print(f"   -> Bomba encontrada: {nome_texto} ({lat:.6f}, {lon:.6f})")

                # Se for uma Linha/Círculo (para pivôs virtuais)
                elif linha_tag is not None and linha_tag.text and "medida do círculo" in nome_lower:
                    coords_texto = linha_tag.text.strip().split()
                    coords_list = []
                    for c in coords_texto:
                        partes = c.split(",")
                        if len(partes) >= 2:
                            coords_list.append([float(partes[1]), float(partes[0])]) # [lat, lon]
                    if coords_list:
                        ciclos.append({"nome": nome_texto, "coordenadas": coords_list})
                        print(f"   -> Círculo encontrado: {nome_texto}")

            # Remove o arquivo KML extraído após o parsing
            os.remove(caminho_kml)

    except Exception as e:
        print(f"❌ Erro ao processar KMZ: {e}")
        raise # Re-lança a exceção para ser tratada no endpoint

    # --- Cria Pivôs Virtuais a partir dos Círculos ---
    nomes_existentes = {normalizar_nome(p["nome"]) for p in pivos}
    contador_virtual = 1

    for ciclo in ciclos:
        nome_ciclo = ciclo.get("nome", "").strip()
        coords_ciclo = ciclo.get("coordenadas", [])
        if not nome_ciclo or not coords_ciclo: continue

        # Tenta extrair o nome do pivô do nome do círculo
        nome_pivo_base = re.sub(r'medida do círculo\s*', '', nome_ciclo, flags=re.IGNORECASE).strip()
        nome_normalizado = normalizar_nome(nome_pivo_base)

        # Se já existe um pivô com esse nome, pula
        if nome_normalizado in nomes_existentes:
            print(f"   -> Pivô virtual '{nome_pivo_base}' já existe como Placemark. Pulando.")
            continue

        # Calcula o centroide (centro do pivô)
        try:
            coords_lonlat = [(lon, lat) for lat, lon in coords_ciclo]
            num_pontos = len(coords_lonlat)
            if num_pontos >= 3:
                poligono = Polygon(coords_lonlat)
                centroide = poligono.centroid
                centro_lat, centro_lon = centroide.y, centroide.x
            else: # Se não for um polígono, usa a média
                centro_lat = mean([lat for lat, lon in coords_ciclo])
                centro_lon = mean([lon for lat, lon in coords_ciclo])
        except Exception as e:
            print(f"   -> ⚠️ Erro no centroide ({nome_pivo_base}), usando média: {e}")
            centro_lat = mean([lat for lat, lon in coords_ciclo])
            centro_lon = mean([lon for lat, lon in coords_ciclo])

        # Define o nome final do pivô virtual
        nome_final = nome_pivo_base if nome_pivo_base else f"Pivô Virtual {contador_virtual}"
        if not re.search(r"\d", nome_final): # Garante um número se não houver
             nome_final = f"{nome_final} {contador_virtual}"
        contador_virtual += 1


        pivos.append({"nome": nome_final, "lat": centro_lat, "lon": centro_lon})
        print(f"   -> Pivô virtual criado: {nome_final} ({centro_lat:.6f}, {centro_lon:.6f})")


    if not antena:
        print("   -> ⚠️ Nenhuma antena encontrada no KMZ.")
        # Poderia lançar um erro aqui se a antena for obrigatória
        # raise ValueError("Antena não encontrada no KMZ. Verifique o nome ('antena', 'torre', etc.).")


    print(f"   -> Processamento concluído: {len(pivos)} pivôs, {len(bombas)} bombas.")
    return antena, pivos, ciclos, bombas