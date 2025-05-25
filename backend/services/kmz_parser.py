import zipfile
import os
import re
import xml.etree.ElementTree as ET
from statistics import mean
from shapely.geometry import Polygon # Certifique-se que 'shapely' está no requirements.txt
from math import sqrt

# --- Funções Auxiliares ---

def normalizar_nome(nome: str) -> str:
    """Remove caracteres especiais, espaços extras e converte para minúsculas."""
    if not nome:
        return ""
    nome = nome.lower()
    nome = re.sub(r'[^a-z0-9À-ú ]', '', nome) # Mantém letras acentuadas e espaços
    nome = re.sub(r'\s+', ' ', nome).strip() # Remove espaços extras
    return nome

# --- Função Principal de Parsing ---

def parse_kmz(caminho_kmz: str, pasta_extracao: str) -> tuple:
    """
    Processa um arquivo KMZ, extrai o KML e retorna os dados geográficos.
    """
    antena = None
    pivos_de_pontos = [] # Pivôs explicitamente definidos como <Point>
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
                            coords_para_ciclo.append([float(partes[1]), float(partes[0])]) # [lat, lon]
                    if coords_para_ciclo:
                        ciclos.append({"nome_original_circulo": nome_texto_original, "coordenadas": coords_para_ciclo})
                        print(f"   -> Círculo encontrado: {nome_texto_original}")
            
            if os.path.exists(caminho_kml_completo):
                os.remove(caminho_kml_completo)

    except Exception as e:
        print(f"❌ Erro ao processar KMZ: {e}")
        raise

    # --- Consolidação dos Pivôs (Pontos + Virtuais dos Círculos) ---
    final_pivos_list = list(pivos_de_pontos) # Começa com os pivôs de pontos
    # Nomes normalizados de todos os pivôs já adicionados (para garantir unicidade)
    todos_nomes_pivos_finais_normalizados = {normalizar_nome(p["nome"]) for p in final_pivos_list}
    
    virtual_pivot_counter = 1

    for ciclo_data in ciclos:
        nome_circulo = ciclo_data["nome_original_circulo"]
        coordenadas_ciclo = ciclo_data["coordenadas"]

        # Tenta derivar um nome de pivô a partir do nome do círculo
        # Remove "medida do círculo" e ajusta para ter "Pivô " no início se não tiver
        nome_pivo_derivado = re.sub(r'medida do círculo\s*', '', nome_circulo, flags=re.IGNORECASE).strip()
        if nome_pivo_derivado and not (nome_pivo_derivado.lower().startswith("pivô ") or nome_pivo_derivado.lower().startswith("pivo ")):
            nome_pivo_derivado = f"Pivô {nome_pivo_derivado}"
        elif not nome_pivo_derivado: # Se ficou vazio, não tem nome derivável
             nome_pivo_derivado = ""


        nome_pivo_derivado_normalizado = normalizar_nome(nome_pivo_derivado)

        # 1. Verifica se já existe um Pivô de PONTO com este nome derivado
        if nome_pivo_derivado_normalizado and nome_pivo_derivado_normalizado in {normalizar_nome(p["nome"]) for p in pivos_de_pontos}:
            print(f"   -> Círculo '{nome_circulo}' corresponde ao Pivô de Ponto explícito '{nome_pivo_derivado}'. Pulando criação virtual.")
            continue

        # Se chegamos aqui, o círculo não corresponde a um Pivô de Ponto existente pelo nome.
        # Então, vamos criar um pivô virtual. Primeiro, calcular o centroide.
        centro_lat, centro_lon = 0.0, 0.0
        try:
            coords_lonlat = [(lon, lat) for lat, lon in coordenadas_ciclo]
            num_pontos_no_ciclo = len(coords_lonlat)
            if num_pontos_no_ciclo == 0:
                print(f"   -> ⚠️ Círculo '{nome_circulo}' sem coordenadas válidas.")
                continue
            if num_pontos_no_ciclo >= 3 and Polygon(coords_lonlat).is_valid: # Precisa de pelo menos 3 para polígono
                poligono = Polygon(coords_lonlat)
                centroide = poligono.centroid
                centro_lat, centro_lon = centroide.y, centroide.x
            else: # Média para linhas ou poucos pontos
                centro_lat = mean([lat for lat, lon in coordenadas_ciclo])
                centro_lon = mean([lon for lat, lon in coordenadas_ciclo])
        except Exception as e:
            print(f"   -> ⚠️ Erro no cálculo do centroide para '{nome_circulo}', usando média: {e}")
            if not coordenadas_ciclo: continue
            centro_lat = mean([lat for lat, lon in coordenadas_ciclo])
            centro_lon = mean([lon for lat, lon in coordenadas_ciclo])

        # Determina o nome final para o pivô virtual
        nome_final_para_virtual = ""
        if nome_pivo_derivado_normalizado and nome_pivo_derivado_normalizado not in todos_nomes_pivos_finais_normalizados:
            nome_final_para_virtual = nome_pivo_derivado
        else:
            # Se o nome derivado não for útil ou já existir, usa nomenclatura padrão "Pivô N"
            while True:
                nome_tentativa = f"Pivô {virtual_pivot_counter}"
                nome_tentativa_normalizado = normalizar_nome(nome_tentativa)
                if nome_tentativa_normalizado not in todos_nomes_pivos_finais_normalizados:
                    nome_final_para_virtual = nome_tentativa
                    virtual_pivot_counter += 1
                    break
                virtual_pivot_counter += 1
                if virtual_pivot_counter > len(ciclos) + len(pivos_de_pontos) + 100: # Safety break
                    print(f"Erro: Loop infinito ao tentar nomear pivô virtual para '{nome_circulo}'")
                    nome_final_para_virtual = f"Pivô Erro {uuid.uuid4().hex[:6]}" # Nome único de fallback
                    break
        
        final_pivos_list.append({"nome": nome_final_para_virtual, "lat": centro_lat, "lon": centro_lon})
        todos_nomes_pivos_finais_normalizados.add(normalizar_nome(nome_final_para_virtual))
        print(f"   -> Pivô virtual criado: '{nome_final_para_virtual}' ({centro_lat:.6f}, {centro_lon:.6f}) a partir de '{nome_circulo}'")

    if not antena:
        print("   -> ⚠️ Nenhuma antena (torre, etc.) encontrada no KMZ.")
        # Você pode querer lançar um erro se a antena for absolutamente necessária
        # raise ValueError("Antena principal não encontrada no KMZ.")

    print(f"   -> Processamento KMZ concluído: {len(final_pivos_list)} pivôs totais, {len(bombas)} bombas.")
    return antena, final_pivos_list, ciclos, bombas # Retorna a lista consolidada