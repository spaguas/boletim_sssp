import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import requests
import os
from osgeo import gdal, ogr, osr
from rasterstats import zonal_stats
import geopandas as gpd
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
import numpy as np
from datetime import datetime, timedelta, time
from PIL import Image, ImageOps
import plotly.express as px
import folium
from branca.element import Element
from streamlit.components.v1 import html
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from PIL import Image
import io
from io import BytesIO
import psycopg2 as pg
import matplotlib.cm as cm
from matplotlib import pyplot as plt
import time as tm
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support import expected_conditions as EC
import urllib.parse
import base64
import asyncio
import plotly.graph_objects as go
from matplotlib.colors import Normalize, rgb2hex
import branca.colormap as cmb
from bs4 import BeautifulSoup
from dotenv import load_dotenv

st.set_page_config(layout="wide")

capa_boletim_container = st.container()
capa_container = st.container()
slide1_secas = st.container()
slide1_container = st.container()
slide2_container = st.container()
slide3_container = st.container()
slide4_container = st.container()
slide5_secas = st.container()
slide5_container = st.container()
slide6_container = st.container()
slide6_secas = st.container()
slide7_container = st.container()
slide8_container = st.container()
slide8_secas = st.container()

load_dotenv()

def conection_postgres():
    host = os.environ.get('DATABASE_HOST')
    port = os.environ.get('DATABASE_PORT')
    user = os.environ.get('DATABASE_USER')
    password = os.environ.get('DATABASE_PASSWORD')
    database = os.environ.get('DATABASE_NAME')    

    conn = pg.connect(
        host=host,
        database=database,
        user=user,
        password=password
    )
    return conn.cursor()

def execute_query(query):
    cur = conection_postgres()
    conn = cur.connection

    try:
        cur.execute(query)
        rows = cur.fetchall()
        
        colunas = [desc[0] for desc in cur.description]
        print("Antes do dataframe -", datetime.now())
        df = pd.DataFrame(rows, columns=colunas)
        print("Depois do dataframe -", datetime.now())

        return df

    except Exception as e:
        print(f"Erro ao executar a query: {e}")
        return None

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

def gerar_mapa_chuva_shapefile(excluir_prefixos, get_data, data_shapefile, arquivo, ):

    data_inicial = datetime.today()
    hora_inicial = time(10, 0)
    data_hora_inicial = datetime.combine(data_inicial, hora_inicial)
    data_inicial_str = data_hora_inicial.strftime('%Y-%m-%d')
    hora_inicial_str = data_hora_inicial.strftime('%H:%M')

    horas = 24

    data_hora_final = data_hora_inicial - timedelta(hours=horas)
    date_time_id = data_hora_inicial.strftime("%Y%m%d%H%M")

    url = f'https://cth.daee.sp.gov.br/sibh/api/v1/measurements/last_hours_events?hours={horas}&from_date={data_inicial_str}T{hora_inicial_str}&show_all=true'
    titulo = f"Acumulado de chuvas de {data_hora_final} à {data_hora_inicial}"
    estatistica_desejada = "mean"

    minx, miny, maxx, maxy = get_data.total_bounds

    get_data.to_file(data_shapefile)

    # Obtendo dados da API
    response = requests.get(url)
    data = response.json()

    # Extraindo coordenadas e valores
    stations = [
        (item["prefix"], float(item["latitude"]), float(item["longitude"]), item["value"])
        for item in data["json"]
        if item["latitude"] and item["longitude"] and item["value"]
    ]

    # Filtrando estações
    filtered_stations = [
        (lat, lon, value)
        for prefix, lat, lon, value in stations
        if prefix not in excluir_prefixos
    ]

    if not filtered_stations:
        st.error("Erro: Não há dados válidos para interpolação após a exclusão.")
        return

    # Separando latitudes, longitudes e valores
    lats, longs, values = zip(*filtered_stations)

    # Salvando os pontos em um shapefile temporário
    shapefile_path = "results/temp_points.shp"
    driver = ogr.GetDriverByName("ESRI Shapefile")
    dataSource = driver.CreateDataSource(shapefile_path)
    layer = dataSource.CreateLayer("layer", geom_type=ogr.wkbPoint)

    # Adicionando valores de precipitação
    layer.CreateField(ogr.FieldDefn("value", ogr.OFTReal))
    for lat, lon, value in zip(lats, longs, values):
        point = ogr.Geometry(ogr.wkbPoint)
        point.AddPoint(lon, lat)
        feature = ogr.Feature(layer.GetLayerDefn())
        feature.SetGeometry(point)
        feature.SetField("value", value)
        layer.CreateFeature(feature)
        feature = None

    dataSource = None

    power = 2.0

    smoothing = 0.02

    radius = 50/100

    output_raster = f"results/{arquivo}_{date_time_id}.tif"
    gdal.Grid(
        output_raster,
        shapefile_path,
        zfield="value",
        algorithm=f"invdist:power={power}:smoothing={smoothing}:radius={radius}",
        outputBounds=(minx, miny, maxx, maxy),
        width=1000, height=1000,
        #options=["noData=-9999"]  # Defina um noData explícito diferente de zero
    )

    if not os.path.exists(output_raster):
        st.error(f"Erro: O raster intermediário {output_raster} não foi criado.")
        return

    # Definindo sistema de coordenadas EPSG:4326 no raster
    raster = gdal.Open(output_raster, gdal.GA_Update)
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    raster.SetProjection(srs.ExportToWkt())
    raster = None

    # Zonal stats
    stats = zonal_stats(get_data, output_raster, stats=[estatistica_desejada], geojson_out=True)
    
    crs = {'init': 'epsg:4326'}
    data_stats = gpd.GeoDataFrame.from_features(stats, crs=crs)
    data_stats = data_stats.rename(columns={estatistica_desejada: f"{estatistica_desejada}_precipitation"})

    # Converte os dados de precipitação para tipo float, preenchendo NaNs com zero
    data_stats[f"{estatistica_desejada}_precipitation"] = pd.to_numeric(
        data_stats[f"{estatistica_desejada}_precipitation"], errors='coerce'
    ).fillna(0)
    

    data_stats_shp = data_stats.rename(columns={f"{estatistica_desejada}_precipitation": "rain"})
    data_stats_shp.to_file(f"./results/acumulado_24_mun_{data_hora_final.strftime('%Y-%m-%d')}.shp", driver="ESRI Shapefile")

    return data_stats

    
def definir_cor(valor):
    if valor < 10:
        return "#16c995"
    elif 10 <= valor < 30:
        return "#fcb900"
    elif 30 <= valor < 70:
        return "#ff7b00"
    else:
        return "#f74f78"

def capturar_tela(url, largura=1500, altura=4000):
    # Configurar o WebDriver do Chrome
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # Executar em modo headless (sem interface gráfica)
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size={},{}".format(largura, altura))
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.get(url)

    tm.sleep(2)
    
    screenshot = driver.get_screenshot_as_png()
    
    driver.quit()
    
    imagem = Image.open(io.BytesIO(screenshot))
    
    return imagem


def classify_state(row):
    value = row['value']
    
    # Verifica cada nível na ordem de prioridade, apenas se não for nulo
    if not pd.isna(row.get('extravasation_level')) and value >= row['extravasation_level']:
        return 'Extravasamento'
    elif not pd.isna(row.get('emergency_level')) and value >= row['emergency_level']:
        return 'Emergência'
    elif not pd.isna(row.get('alert_level')) and value >= row['alert_level']:
        return 'Alerta'
    elif not pd.isna(row.get('attention_level')) and value >= row['attention_level']:
        return 'Atenção'
    else:
        # Se todos os níveis forem nulos ou o valor for menor que attention_level
        if pd.isna([row['extravasation_level'], row['emergency_level'], 
                   row['alert_level'], row['attention_level']]).all():
            return 'Níveis Indefinidos'
        else:
            return 'Normal'
        
def classify_state_seca(row):
    value = row['value']
    
    # Verifica cada nível na ordem de prioridade, apenas se não for nulo
    if not pd.isna(row.get('l95')) and value <= row['l95']:
        return 'Atenção - l95'
    else:
        # Se todos os níveis forem nulos ou o valor for menor que attention_level
        if pd.isna([row['l95']]).all():
            return 'Níveis Indefinidos'
        else:
            return 'Normal'
        
def get_fill_color(status):
    status = status['properties']['status']  # Acessa o valor de 'status' da feição

    if status == 'Normal':
        return '#16c995'  # Verde
    elif status == 'Atenção':
        return '#bda501'  # Laranja
    else:
        return '#737491'
    
def get_fill_color_secas(status):
    status = status['properties']['cs_chuva']
    if status < 5:
        return '#a2f5e9'
    elif status < 10:
        return '#8ff29b'
    elif  status < 30:
        return '#5ab53c'
    elif status < 50:
        return '#d1fb47'
    elif status < 80:
        return '#faa247'
    elif status < 120:
        return '#ea311f'
    elif 120 <= status :
        return '#cd12b6'
    else:
        return '#a2f5e9'
    
def get_fill_color_secas_dsc(status):
    status = status['properties']['dsc'] 
    if status < 10:
        return '#a2f5e9'
    elif status < 30:
        return '#8ff29b'
    elif  status < 50:
        return '#5ab53c'
    elif status < 80:
        return '#d1fb47'
    elif status < 120:
        return '#faa247'
    elif status < 160:
        return '#ea311f'
    elif 160 <= status :
        return '#cd12b6'
    else:
        return '#a2f5e9'

def barra_colorida(val):
    try:
        pct = float(val)
    except:
        return str(val)

    # Normalizar valor entre 0 e 1
    norm = Normalize(vmin=0, vmax=100)
    cmap = cm.get_cmap('Wistia')

    gradientes = []
    n_blocos = 10
    largura_bloco = 10

    for i in range(n_blocos):
        bloco_inicio = i * largura_bloco
        bloco_fim = (i + 1) * largura_bloco
        cor = rgb2hex(cmap(norm(bloco_inicio))) if pct >= bloco_inicio else "transparent"
        gradientes.append(f"{cor} {bloco_inicio}%, {cor} {bloco_fim}%")

    gradiente_css = ", ".join(gradientes)

    return f"""
        display: flex;
        justify-content: end;
        align-items: right;
        background: linear-gradient(to right, {gradiente_css});
        padding: 0 5px;
        color: black;
    """

def colorir_status(valor):
    if valor == 'Normal':
        return 'background-color: green; color: white;'
    elif valor == 'Atenção':
        return 'background-color: yellow; color: black;'
    elif valor == 'Alerta':
        return 'background-color: orange; color: white;'
    elif valor == 'Emergência':
        return 'background-color: red; color: white;'
    else:
        return ''

# CSS personalizado para fundo branco e estilo dos slides
st.markdown(
    """
    <style>
    /* Limita a largura máxima do contêiner para evitar overflow */
    .main .block-container {
        max-width: 100%;  /* Ajuste para garantir a largura adequada */
    }

    /* Define o fundo da página como branco */
    body {
        background-color: white !important;  /* Mantém o fundo branco */
    }

    /* Remove a margem do corpo e ajusta o conteúdo */
    body, .stApp {
        margin: 0;
        padding: 0;
    }

    /* Altera a cor do título */
    .custom-title {
        color: #333333; /* Laranja */
        font-size: 1.5rem; /* Tamanho do título */
        font-weight: bold; /* Negrito */
    }

    /* Altera a cor do texto normal */
    p {
        color: #333333; /* Cinza escuro */
    }

    /* Define o fundo dos contêineres do Streamlit como branco */
    .stApp {
        background-color: white !important;
    }

    .align-left-center {
        display: flex;
        align-items: center;  /* Centraliza verticalmente */
        justify-content: flex-start;  /* Alinha o texto à esquerda */
        height: 100%;  /* Garante que o contêiner ocupe toda a altura da coluna */
    }

    .stTextArea label {
        font-size: 12px !important;  /* Tamanho da fonte */
        color: #333333 !important;   /* Cor azul moderna */
        font-weight: bold !important;
    }

    .stTextArea textarea {
        border-radius: 5px;
        background-color: white;
        font-size: 12px;
        color: #333333; 
        line-height: 1.6;
        
    }

    .editable-box:hover {
        background-color: #f0f0f0;
    }
    </style>
    """,
    unsafe_allow_html=True
)

def get_base64_image(image_path):
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()
    
# Função para a capa
async def capa():
    print("Capa -", datetime.now())
    with capa_container:

        colcenter1, colcenter2 = st.columns([1.50, 0.50])

        with colcenter1:
            bg_base64 = get_base64_image("Logo Colorido.png")
            sp4_base64 = get_base64_image("SP-4.png")
            gov_base64 = get_base64_image("regua.png")

            data_atual = datetime.today()
            data_anterior = datetime.today() - timedelta(days=1)
            data_atual_str = data_atual.strftime('%d-%m-%Y').replace('-', '/')
            data_anterior_str = data_anterior.strftime('%d-%m-%Y').replace('-', '/')


            st.markdown(
                f"""
                <style>
                    .relative-container {{
                        position: relative;
                        min-height: 620px;
                        overflow: visible;
                    }}

                    .background-image {{
                        position: absolute;
                        top: -170px;
                        left: 400px;
                        height: 100%;
                        object-fit: cover;
                        opacity: 0.15;
                        z-index: 0;
                    }}

                    .text-content {{
                        position: relative;
                        z-index: 1;
                        color: black;
                        padding: 20px;
                    }}
                </style>

                <div class="relative-container">
                    <img src="data:image/png;base64,{bg_base64}" class="background-image">
                    <div class="text-content" style="margin-top: 200px;">
                        <h1 style="font-size: 50px; margin: 0; padding-top: 120px; font-weight: bold; ">Boletim Diário</h1>
                        <h1 style="font-size: 28px; margin: 0; padding: 0;">Sala de Situação São Paulo - SSSP</h1>
                        <h1 style="font-size: 22px; margin: 0; padding: 0;">({data_anterior_str} 07:00 até {data_atual_str} 07:00)</h1>
                    </div>
                </div>
                <div style="position: absolute; bottom: -100px; right: -380px; display: flex; gap: 20px; z-index: 1;">
                    <img src="data:image/png;base64,{gov_base64}" width="600" height="80">
                </div>
                """,
                unsafe_allow_html=True
            )


        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")



        await asyncio.sleep(1)
    
async def slide1_seca():
    with slide1_secas:

        col1, col2, col3 = st.columns([1.2, 1.5, 0.15])

        with col1:
            st.write("""
                <div class="align-left-center">
                    <div style="color: black;">
                        <p style="font-size: 11px">Agência de Água do Estado de São Paulo</h1>
                    </div>
                </div>
                """,
                    unsafe_allow_html=True)

        with col3:
            st.markdown('<div class="align-right">', unsafe_allow_html=True)
            st.image("spaguas.png", caption="", width=300)
            st.markdown('</div>', unsafe_allow_html=True)

        with col2:
            st.write(f"""
            <div style="color: black;">
                <h1  style="font-size: 16px;">Mapa de dias secos </h1>
            </div>
            """,
            unsafe_allow_html=True)

        query_dias_sem_chuva = f"""select 
                                    c.cod_ibge,
                                    c."name",
                                    SUM(hs.dsc) AS dsc
                                from hidroapp_statistics hs 
                                left join cities c on c.id = hs.model_id
                                where date_hour between '2025-03-01 03:00:00.000' and '2025-09-30 03:00:00.000'and model_type ='City'
                                group by c.cod_ibge, c."name";"""
        
        tabela_dsc_cities= execute_query(query_dias_sem_chuva)



        query_dias_consec_sem_chuva = f"""select 
                                            c."name",
                                            c.cod_ibge,
                                            p.values ->'climate' ->'dsc' AS dcsc_chuva,
                                            cu.ugrhi_id, 
                                            cu.ugrhi_name
                                        from parameters p 
                                        left join cities c on c.id = p.parameterizable_id
                                        left join maps.city_ugrhis cu on cu.city_cod = c.cod_ibge
                                        where p.parameter_type_id ='5' and p.parameterizable_type = 'City';
                                        """

        tabela_dcsc_cities= execute_query(query_dias_consec_sem_chuva)
        tabela_dcsc_cities['dcsc_chuva'] = tabela_dcsc_cities['dcsc_chuva'].astype(float)
        tabela_df = tabela_dcsc_cities.groupby('cod_ibge', as_index=False).agg(
                            value=('name', 'first'),
                            cs_chuva=('dcsc_chuva', 'first')
                        )
        
        grafico_dsc_ugrhi = tabela_dcsc_cities.groupby('ugrhi_id', as_index=False).agg(
            value=('ugrhi_name', 'first'),
            cs_chuva_5=('dcsc_chuva', lambda x: x[x < 5].count()),
            cs_chuva_10=('dcsc_chuva', lambda x: x[x < 10].count()),
            cs_chuva_30=('dcsc_chuva', lambda x: x[x < 30].count()),
            cs_chuva_50=('dcsc_chuva', lambda x: x[x < 50].count()),
            cs_chuva_80=('dcsc_chuva', lambda x: x[x < 80].count()),
            cs_chuva_120=('dcsc_chuva', lambda x: x[x < 120].count()),
            cs_chuva_121=('dcsc_chuva', lambda x: x[x >= 120].count()),
        )

        tabela_df['cs_chuva'] = tabela_df['cs_chuva'].astype(float)        

        shapefile_path = "data/DIV_MUN_SP_2021a.shp"
        gdf = gpd.read_file(shapefile_path)

        merged_data = pd.merge(gdf, tabela_df, left_on='GEOCODIGO', right_on='cod_ibge', how='left')
        merged_tabela_dsc = pd.merge(gdf, tabela_dsc_cities, left_on='GEOCODIGO', right_on='cod_ibge', how='left')
        
        shapefile_path_limite = "data/limiteestadualsp.shp"

        gdf_limite = gpd.read_file(shapefile_path_limite)

        if gdf_limite.crs != "EPSG:4326":
            gdf_limite = gdf_limite.to_crs(epsg=4326)

        latitude =  -22.8859
        longitude = -48.4451

        merged_data = merged_data.to_crs(epsg=4326)
        merged_tabela_dsc = merged_tabela_dsc.to_crs(epsg=4326)

        coluna1, coluna2 = st.columns([1.0, 1.0])
        with coluna1:
            mapa_dsc = folium.Map(
                location=[latitude, longitude],  # Centralizar no meio dos pontos
                zoom_start=5.5,
                tiles=None,
                control_scale=False, 
                zoomControl=False
            )

            folium.TileLayer(
                tiles='https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
                attr=' ',
                name='OpenStreetMap',
                overlay=False,
                control=True, 
            ).add_to(mapa_dsc)

            mapa_dsc.options['attributionControl'] = False
            
            geojson_data_dsc = merged_tabela_dsc.to_json()  
            
            folium.GeoJson(
                geojson_data_dsc,
                name='Shapefile',
                style_function=lambda x: {
                    'fillColor': get_fill_color_secas_dsc(x),
                    'color': 'black',     
                    'weight': 0.3,          
                    'fillOpacity': 0.6    
                }
            ).add_to(mapa_dsc)
            
            legenda_html = """
            <div style="position: fixed; z-index:999999; bottom: 10px; left: 50%; transform: translateX(-50%); background: white; padding: 2px; border-radius: 5px; box-shadow: 0 0 3px rgba(0,0,0,0.3); display: flex; align-items: center; justify-content: center;">
                <div style="display: flex; align-items: center; margin-right: 5px;">
                    <div style="width: 50px; height: 15px; background-color: #a2f5e9; display: flex; align-items: center; justify-content: center; color: #2E2E2E; font-size: 8px; border-radius: 3px;">
                        <span> > 10 </span>
                    </div>
                </div>
                <div style="display: flex; align-items: center; margin-right: 5px;">
                    <div style="width: 50px; height: 15px; background-color: #5ab53c; display: flex; align-items: center; justify-content: center; color: #2E2E2E; font-size: 8px; border-radius: 3px;">
                        <span> 10 >< 30 </span>
                    </div>   
                </div>
                <div style="display: flex; align-items: center; margin-right: 5px;">
                    <div style="width: 50px; height: 15px; background-color: #54f267; display: flex; align-items: center; justify-content: center; color: #2E2E2E; font-size: 8px; border-radius: 3px;">
                        <span> 30 >< 50 </span>
                    </div>
                </div>
                <div style="display: flex; align-items: center; margin-right: 5px;">
                    <div style="width: 50px; height: 15px; background-color: #d1fb47; display: flex; align-items: center; justify-content: center; color: #2E2E2E; font-size: 8px; border-radius: 3px;">
                        <span> 50 >< 80 </span>
                    </div>
                </div>
                <div style="display: flex; align-items: center; margin-right: 5px;">
                    <div style="width: 50px; height: 15px; background-color: #faa247; display: flex; align-items: center; justify-content: center; color: #2E2E2E; font-size: 8px; border-radius: 3px;">
                        <span> 80 >< 120 </span>
                    </div>
                </div>
                <div style="display: flex; align-items: center; margin-right: 5px;">
                    <div style="width: 50px; height: 15px; background-color: #ea311f; display: flex; align-items: center; justify-content: center; color: #2E2E2E; font-size: 8px; border-radius: 3px;">
                        <span> 120 >< 160 </span>
                    </div>
                </div>
                <div style="display: flex; align-items: center; margin-right: 5px;">
                    <div style="width: 50px; height: 15px; background-color: #cd12b6; display: flex; align-items: center; justify-content: center; color: #2E2E2E; font-size: 8px; border-radius: 3px;">
                        <span> > >160 </span>
                    </div>
                </div>
            </div>
            """

            mapa_dsc.get_root().html.add_child(Element(legenda_html))

            mapa_html_dsc = mapa_dsc._repr_html_()

            st.write("""
                <div style="text-align: center; color: #333333;">
                    <h1  style="font-size: 10px; margin: 0; padding: 0">Dias sem chuva no período de estiagem (01/04 a 30/09)</h1>
                </div>
                """,
            unsafe_allow_html=True)
            st.components.v1.html(mapa_html_dsc, width=600, height=350)

            url_geodados='https://hidroapp.daee.sp.gov.br/mapa'
            st.write(f"""
                <div style="color: black; line-height: 1;">
                    <p style="text-align: center; font-size: 10px; margin: 0; padding: 0;">Elaborado pela equipe do SP Águas. Disponível em: <a href="{url_geodados}" target="_blank"> Hidroapp</a></p>
                </div>
                """,
            unsafe_allow_html=True) 

        with coluna2:
            mapa = folium.Map(
                location=[latitude, longitude],  # Centralizar no meio dos pontos
                zoom_start=6,
                tiles=None,
                control_scale=False, 
                zoomControl=False
            )

            folium.TileLayer(
                tiles='https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
                attr=' ',
                name='OpenStreetMap',
                overlay=False,
                control=True, 
            ).add_to(mapa)

            mapa.options['attributionControl'] = False

            geojson_data = merged_data.to_json()  
            
            folium.GeoJson(
                geojson_data,
                name='Shapefile',
                style_function=lambda x: {
                    'fillColor': get_fill_color_secas(x),  # Cor de preenchimento
                    'color': 'black',     # Cor da borda
                    'weight': 0.3,          # Espessura da borda
                    'fillOpacity': 0.6    # Transparência do preenchimento
                }
            ).add_to(mapa)
            
            legenda_html = """
            <div style="position: fixed; z-index:999999; bottom: 10px; left: 50%; transform: translateX(-50%); background: white; padding: 2px; border-radius: 5px; box-shadow: 0 0 3px rgba(0,0,0,0.3); display: flex; align-items: center; justify-content: center;">
                <div style="display: flex; align-items: center; margin-right: 5px;">
                    <div style="width: 50px; height: 15px; background-color: #a2f5e9; display: flex; align-items: center; justify-content: center; color: #2E2E2E; font-size: 8px; border-radius: 3px;">
                        <span> > 5 </span>
                    </div>
                </div>
                <div style="display: flex; align-items: center; margin-right: 5px;">
                    <div style="width: 50px; height: 15px; background-color: #90f29c; display: flex; align-items: center; justify-content: center; color: #2E2E2E; font-size: 8px; border-radius: 3px;">
                        <span> 5 >< 10 </span>
                    </div>   
                </div>
                <div style="display: flex; align-items: center; margin-right: 5px;">
                    <div style="width: 50px; height: 15px; background-color: #5ab53c; display: flex; align-items: center; justify-content: center; color: #2E2E2E; font-size: 8px; border-radius: 3px;">
                        <span> 10 >< 30 </span>
                    </div>
                </div>
                <div style="display: flex; align-items: center; margin-right: 5px;">
                    <div style="width: 50px; height: 15px; background-color: #d1fb47; display: flex; align-items: center; justify-content: center; color: #2E2E2E; font-size: 8px; border-radius: 3px;">
                        <span> 30 >< 50 </span>
                    </div>
                </div>
                <div style="display: flex; align-items: center; margin-right: 5px;">
                    <div style="width: 50px; height: 15px; background-color: #faa247; display: flex; align-items: center; justify-content: center; color: #2E2E2E; font-size: 8px; border-radius: 3px;">
                        <span> 50 >< 80 </span>
                    </div>
                </div>
                <div style="display: flex; align-items: center; margin-right: 5px;">
                    <div style="width: 50px; height: 15px; background-color: #ea311f; display: flex; align-items: center; justify-content: center; color: #2E2E2E; font-size: 8px; border-radius: 3px;">
                        <span> 80 >< 120 </span>
                    </div>
                </div>
                <div style="display: flex; align-items: center; margin-right: 5px;">
                    <div style="width: 50px; height: 15px; background-color: #cd12b6; display: flex; align-items: center; justify-content: center; color: #2E2E2E; font-size: 8px; border-radius: 3px;">
                        <span> > >120 </span>
                    </div>
                </div>
            </div>
            """

            mapa.get_root().html.add_child(Element(legenda_html))

            mapa_html = mapa._repr_html_()
            st.write("""
                <div style="text-align: center; color: #333333;">
                    <h1  style="font-size: 10px; margin: 0; padding: 0">Dias consecutivos sem chuva</h1>
                </div>
                """,
            unsafe_allow_html=True)
            st.components.v1.html(mapa_html, width=600, height=350)
            url_geodados='https://hidroapp.daee.sp.gov.br/mapa'
            st.write(f"""
                <div style="color: black; line-height: 1;">
                    <p style="text-align: center; font-size: 10px; margin: 0; padding: 0;">Elaborado pela equipe do SP Águas. Disponível em: <a href="{url_geodados}" target="_blank"> Hidroapp</a></p>
                </div>
                """,
            unsafe_allow_html=True) 
                    

        st.write(" ")
        st.write(" ")

        data_dsc = merged_tabela_dsc[['NOME', 'dsc']]
        data_dsc= data_dsc.rename(columns={"NOME":"Município", "dsc": "DSC"})
        data_dsc = data_dsc.sort_values(by='DSC', ascending=False)
        data_dsc = data_dsc.head(10).reset_index(drop=True)

        data_dcsc = merged_data[['NOME', 'cs_chuva']]
        data_dcsc= data_dcsc.rename(columns={"NOME":"Município", "cs_chuva": "DCSC"})
        data_dcsc = data_dcsc.sort_values(by='DCSC', ascending=False)
        data_dcsc = data_dcsc.head(10).reset_index(drop=True)

        legenda = ''
        c1, c2, c3 = st.columns([0.2, 1.2, 0.2])

        with c2:
            if 'user_input_slide1_seca' not in st.session_state:
                st.session_state.user_input_slide1_seca = "Clique para editar"
            
            user_input = st.text_area("Relatos 24h", value=st.session_state.user_input_slide1_seca, height=200, key="user_input_slide1_seca")
                   
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")

    
        colun1, colun2, colun3 = st.columns([1.2, 1.5, 0.15])

        with colun1:
            st.write("""
                <div class="align-left-center">
                    <div style="color: black;">
                        <p style="font-size: 11px">Agência de Água do Estado de São Paulo</h1>
                    </div>
                </div>
                """,
                    unsafe_allow_html=True)

        with colun3:
            st.markdown('<div class="align-right">', unsafe_allow_html=True)
            st.image("spaguas.png", caption="", width=300)
            st.markdown('</div>', unsafe_allow_html=True)

        with colun2:
            st.write(f"""
            <div style="color: black;">
                <h1  style="font-size: 16px;">Mapa de dias secos </h1>
            </div>
            """,
            unsafe_allow_html=True)



        colun1, colun2 = st.columns([1.0, 1.0])
        
        with colun1:
            styled_df = data_dsc.style\
            .format({
                    'DSC': '{:.0f}'
                })\
            .hide(axis="index")\
            .set_caption("Dias sem chuva (DSC) por Município")\
            .set_table_styles([
                {"selector": "caption", "props": [
                    ("color", "black"),
                    ("font-size", "12px"),
                    ("font-weight", "bold"),
                    ("text-align", "center"),
                    ("padding", "5px"),
                    ("caption-side", "top") 
                ]},
                {"selector": "th", "props": [
                    ("font-size", "12px"), 
                    ("background-color", "#f0f0f0"),
                    ("color", "#333333"),
                    ("padding", "5px"),
                    ("height", "8px"),
                    ("text-align", "center")
                    ]},
                {"selector": "td", "props": [
                    ("font-size", "12px"),
                    ("height", "6px"),
                    ("color", "#333333"),
                    ("padding", "2px 4px"),
                    ("text-align", "center"),
                    ("width", "100px")
                    # ("border-bottom", "1px solid #e0e0e0")
                    ]},
                {"selector": "tr:hover", "props": [(
                    "background-color", "#ffff99"),
                    ("cursor", "pointer"),
                ]},
                {"selector": "th.col0", "props": [("width", "300px")]},
                {"selector": "td.col0", "props": [("width", "300px")]},
                {"selector": "th.col1", "props": [("width", "200px")]},
                {"selector": "td.col1", "props": [("width", "200px")]}
            ])\
            .set_properties(**{"background-color": "#f9f9f9", "color": "#333333"})
                    
            st.markdown(styled_df.to_html(), unsafe_allow_html=True)
            st.write(" ")
            # st.write("""  
            #         <div style="color: black; line-height: 1;">
            #             <p style="font-size: 12px; margin: 0.5; padding: 0;">DS - Dias sem chuva</p>
            #         </div>
            #         """,
            #         unsafe_allow_html=True)
                
        with colun2:
            styled_df = data_dcsc.style\
            .format({
                    'DCSC': '{:.0f}'
                })\
            .hide(axis="index")\
            .set_caption("Dias consecutivos sem chuva (DCSC) por Município")\
            .set_table_styles([
                {"selector": "caption", "props": [
                    ("color", "black"),
                    ("font-size", "12px"),
                    ("font-weight", "bold"),
                    ("text-align", "center"),
                    ("padding", "5px"),
                    ("caption-side", "top") 
                ]},
                {"selector": "th", "props": [
                    ("font-size", "12px"), 
                    ("background-color", "#f0f0f0"),
                    ("color", "#333333"),
                    ("height", "8px"),
                    ("padding", "5px"),
                    ("text-align", "center")
                    ]},
                {"selector": "td", "props": [
                    ("font-size", "12px"),
                    ("height", "6px"),
                    ("color", "#333333"),
                    ("padding", "2px 4px"),
                    ("text-align", "center"),
                    ("width", "100px")
                    # ("border-bottom", "1px solid #e0e0e0")
                    ]},
                {"selector": "tr:hover", "props": [(
                    "background-color", "#ffff99"),
                    ("cursor", "pointer")
                ]},
                {"selector": "th.col0", "props": [("width", "300px")]},
                {"selector": "td.col0", "props": [("width", "300px")]},
                {"selector": "th.col1", "props": [("width", "200px")]},
                {"selector": "td.col1", "props": [("width", "200px")]}
            ])\
            .set_properties(**{"background-color": "#f9f9f9", "color": "#333333"})
                    
            st.markdown(styled_df.to_html(), unsafe_allow_html=True)
            # st.write("""  
            #         <div style="color: black; line-height: 1;">
            #             <p style="font-size: 12px; margin: 0.5; padding: 0;">DCSC - Dias consecutivos sem chuva</p>
            #         </div>
            #         """,
            #         unsafe_allow_html=True) 
                
        query_ugrhi = f"""select u.name, 
                            u.cod as ugrhi_id, 
                            count(cu.city_cod) as qtd_city
                        from public.ugrhis u
                        left join maps.city_ugrhis cu on cu.ugrhi_id = u.cod
                        where u.name<>'FORA DO ESTADO DE SÃO PAULO' and u.name<>'Ugrhi não cadastrada'
                        group by u.name,u.cod;"""

        all_ugrhi = execute_query(query_ugrhi)

        tabela_ugrhis_df = pd.merge(all_ugrhi, grafico_dsc_ugrhi, on='ugrhi_id', how='left')

        df_long = tabela_ugrhis_df.melt(
            id_vars=['value', 'qtd_city'],  # 'value' = nome da UGRHI, 'qtd_city' = total de cidades
            value_vars=[
                'cs_chuva_5', 'cs_chuva_10', 'cs_chuva_30',
                'cs_chuva_50', 'cs_chuva_80', 'cs_chuva_120', 'cs_chuva_121'
            ],
            var_name='status_chuva',
            value_name='qtd'
        )

        df_long['status_chuva'] = df_long['status_chuva'].replace({
            'cs_chuva_5': '<5',
            'cs_chuva_10': '<10',
            'cs_chuva_30': '<30',
            'cs_chuva_50': '<50',
            'cs_chuva_80': '<80',
            'cs_chuva_120': '<120',
            'cs_chuva_121': '>=120'
        })
        # Calcular total por UGRHI e % de cada status
        # df_long['total'] = df_long.groupby('value')['qtd'].transform('sum')
        df_long['pct'] = df_long['qtd'] / df_long['qtd_city'] * 100
        df_long['pct'] = df_long['pct'].round(0)
        df_long['text_label'] = df_long['pct'].apply(lambda x: f'{x:.0f}' if x >= 10 else '')

        fig = px.bar(
            df_long, 
            x='value', 
            y='pct', 
            color='status_chuva', 
            text='text_label',
            labels={'pct': '% de cidades', 'value': 'UGRHI'},
            title="""% de cidades com DCSC por UGRHI""",
            color_discrete_map={
                '<5': '#a2f5e9',
                '<10': '#8ff29b',
                '<30': '#54f267',
                '<50': '#d1fb47',
                '<80': '#faa247',
                '<120': '#ea311f',
                '>=120': '#cd12b6'
                # 'Sem chuva': '#FE2E2E',
                # 'Com chuva': '#a2f5e9'   
            }
        )

        fig.update_layout(
            barmode='stack',
            yaxis_tickformat='.0f%%',
            xaxis_tickangle=-45,
            plot_bgcolor='white',
            paper_bgcolor='white',
            height=500,
            bargap=0.5,
            font=dict(size=12, color='#333333'),
            title_font=dict(size=16, color='#333333'),
            title_x=0.3, 
            legend_font=dict(size=12, color='#333333'),
            legend_title_text=' ',
            xaxis=dict(title_font=dict(size=14, color='#333333'), tickfont=dict(size=12, color='#333333')),
            yaxis=dict(title_font=dict(size=14, color='#333333'), tickfont=dict(size=12, color='#333333'), range=[0, 100]),
            legend=dict(
                orientation='h',
                yanchor='bottom',
                y=1.02,
                xanchor='center',
                x=0.5
            )
        )
        fig.update_traces(textposition='inside', texttemplate='%{text}', textfont=dict(size=11, color='#333333'))

        st.plotly_chart(fig, use_container_width=True)


async def slide1():
    print("Rodando 1 -", datetime.now())
    with slide1_container:
        col1, col2, col3 = st.columns([1.2, 1.5, 0.15])

        with col1:
            st.write("""
                <div class="align-left-center">
                    <div style="color: black;">
                        <p style="font-size: 11px">Agência de Água do Estado de São Paulo</h1>
                    </div>
                </div>
                """,
                unsafe_allow_html=True)

        with col3:
            st.markdown('<div class="align-right">', unsafe_allow_html=True)
            st.image("spaguas.png", caption="", width=200)
            st.markdown('</div>', unsafe_allow_html=True)

        with col2:
            st.write("""
            <div style="color: black;">
                <h1  style="font-size: 16px;">Dados Pluviometria</h1>
            </div>
            """,
            unsafe_allow_html=True)


        coluna1, coluna2 = st.columns([1.0, 1.0])

        cmap1, cmap2, coluna3 = st.columns([0.4, 2.0, 0.2])

        colun1, colun2, colun3 = st.columns([0.2, 1.2, 0.2])

        data_inicial = datetime.today()
        hora_inicial = time(10, 0)
        data_hora_inicial = datetime.combine(data_inicial, hora_inicial)
        data_inicial_str = data_hora_inicial.strftime('%Y-%m-%d')
        hora_inicial_str = data_hora_inicial.strftime('%H:%M')

        url = f'https://cth.daee.sp.gov.br/sibh/api/v2/measurements/now?station_type_id=2&hours=24&from_date={data_inicial_str}T{hora_inicial_str}&show_all=true&serializer=complete&public=true'
        
        response = requests.get(url)

        if response.status_code == 200:

            data = response.json()

            if 'measurements' in data and data['measurements']:
                
                df = pd.DataFrame(data['measurements'])

                df['value'] = pd.to_numeric(df['value'], errors='coerce')
                df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce')
                df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')
                df = df.sort_values(by="value", ascending=False)
                
                latitude =  -22.8859
                longitude = -48.4451

                mapa = folium.Map(
                    location=[latitude, longitude],  # Centralizar no meio dos pontos
                    zoom_start=6,
                    tiles=None,
                    control_scale=False, 
                    zoomControl=False,
                )

                folium.TileLayer(
                    tiles='https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
                    attr=' ',
                    name='OpenStreetMap',
                    overlay=False,
                    control=True, 
                ).add_to(mapa)

                mapa.options['attributionControl'] = False
                
                shapefile_path = "data/limiteestadualsp.shp"
                gdf = gpd.read_file(shapefile_path)

                folium.GeoJson(
                    gdf,
                    name='Shapefile',
                    style_function=lambda x: {
                        'fillColor': '#808080',  # Cor de preenchimento
                        'color': 'black',     # Cor da borda
                        'weight': 0.5,          # Espessura da borda
                        'fillOpacity': 0.2    # Transparência do preenchimento
                    }
                ).add_to(mapa)


                layer_10 = folium.FeatureGroup(name='&lt; 10 Mm')
                layer_30 = folium.FeatureGroup(name='10 <> 30 Mm')
                layer_70 = folium.FeatureGroup(name='30 <> 70 Mm')
                layer_100 = folium.FeatureGroup(name='&gt; 70 Mm')

                # Adicionar marcadores para cada ponto
                for index, row in df.iterrows():
                    lat = row['latitude']
                    lon = row['longitude']
                    valor = row['value']
                    valor= round(valor)
                    prefix = row['prefix']

                    cor = definir_cor(valor)

                    valor_inteiro = int(valor)

                    if valor_inteiro > 0:
                        # Criar um popup com o valor
                        popup = f"Prefix: {prefix}"

                        # Definir os marcadores para os diferentes intervalos de valor
                        if valor_inteiro < 10:
                            folium.CircleMarker(
                                location=[lat, lon],
                                radius=6,
                                color="white",  # Borda branca
                                weight=1.5,
                                fill=True,
                                fill_color=cor,
                                fill_opacity=1.0,
                                popup=popup
                            ).add_to(layer_10)

                            folium.Marker(
                                location=[lat, lon],
                                popup=popup,
                                icon=folium.DivIcon(
                                    icon_size=(14, 14),  # Tamanho do ícone
                                    icon_anchor=(7, 7),  # Para centralizar o texto
                                    html=f'<div style="font-size: 8px; color: white; text-align: center; background-color: {cor}; border-radius: 50%; width: 14px; height: 14px; line-height: 14px; border: 1px solid white;">{valor}</div>'
                                )
                            ).add_to(layer_10)

                        elif 10 <= valor_inteiro < 30:
                            folium.CircleMarker(
                                location=[lat, lon],
                                radius=6,
                                color="white",
                                weight=1.5,
                                fill=True,
                                fill_color=cor,
                                fill_opacity=1.0,
                                popup=popup
                            ).add_to(layer_30)

                            folium.Marker(
                                location=[lat, lon],
                                icon=folium.DivIcon(
                                    icon_size=(14, 14),  # Tamanho do ícone
                                    icon_anchor=(7, 7),  # Para centralizar o texto
                                    html=f'<div style="font-size: 8px; color: white; text-align: center; background-color: {cor}; border-radius: 50%; width: 14px; height: 14px; line-height: 14px; border: 1px solid white;">{valor}</div>'
                                )
                            ).add_to(layer_30)

                        elif 30 <= valor_inteiro < 70:
                            folium.CircleMarker(
                                location=[lat, lon],
                                radius=6,
                                color="white",
                                weight=1.5,
                                fill=True,
                                fill_color=cor,
                                fill_opacity=1.0,
                                popup=popup
                            ).add_to(layer_70)

                            folium.Marker(
                                location=[lat, lon],
                                icon=folium.DivIcon(
                                    icon_size=(14, 14),  # Tamanho do ícone
                                    icon_anchor=(7, 7),  # Para centralizar o texto
                                    html=f'<div style="font-size: 8px; color: white; text-align: center; background-color: {cor}; border-radius: 50%; width: 14px; height: 14px; line-height: 14px; border: 1px solid white;">{valor}</div>'
                                )
                            ).add_to(layer_70)
                            

                        else:  # Se for maior que 70
                            folium.CircleMarker(
                                location=[lat, lon],
                                radius=6,
                                color="white",
                                weight=1.5,
                                fill=True,
                                fill_color=cor,
                                fill_opacity=1.0,
                                popup=popup
                            ).add_to(layer_100)

                            folium.Marker(
                                location=[lat, lon],
                                icon=folium.DivIcon(
                                    icon_size=(14, 14),  # Tamanho do ícone
                                    icon_anchor=(7, 7),  # Para centralizar o texto
                                    html=f'<div style="font-size: 8px; color: white; text-align: center; background-color: {cor}; border-radius: 50%; width: 14px; height: 14px; line-height: 14px; border: 1px solid white;">{valor}</div>'
                                )
                            ).add_to(layer_100)

                layer_10.add_to(mapa)
                layer_30.add_to(mapa)
                layer_70.add_to(mapa)
                layer_100.add_to(mapa)
                folium.LayerControl().add_to(mapa)


                legenda_html = """
                    <div style="position: absolute; z-index: 999999; bottom: 10px; left: 50%; transform: translateX(-50%); display: flex; align-items: center; justify-content: center; font-size: 12px; background-color: white; padding: 5px; opacity: 1.0; border-radius:5px; font-size:12px; box-shadow: 0 2px 6px rgba(0,0,0,0.3);">
                        <div style="display: flex; align-items: center; margin-right: 5px;">
                            <div  style="width: 50px; height: 15px; background-color: #16c995; display: flex; align-items: center; justify-content: center; color: white; font-size: 8px; border-radius: 3px;">
                                <span>&lt; 10 Mm</span>
                            </div>
                        </div>
                        <div style="display: flex; align-items: center; margin-right: 5px;">
                            <div style="width: 50px; height: 15px; background-color: #fcb900; display: flex; align-items: center; justify-content: center; color: white; font-size: 8px; border-radius: 3px;">
                                <span>10 <> 30 Mm</span>
                            </div>   
                        </div>
                        <div style="display: flex; align-items: center; margin-right: 5px;">
                            <div style="width: 50px; height: 15px; background-color: #ff7b00; display: flex; align-items: center; justify-content: center; color: white; font-size: 8px; border-radius: 3px;">
                                <span>30 <> 70 Mm</span>
                            </div>
                        </div>
                        <div style="display: flex; align-items: center;">
                            <div style="width: 50px; height: 15px; background-color: #f74f78; display: flex; align-items: center; justify-content: center; color: white; font-size: 8px; border-radius: 3px;">
                                <span>> 70 Mm</span>
                            </div>
                        </div>
                    </div>
                """
                
                # # Adicionar a legenda ao mapa
                mapa.get_root().html.add_child(Element(legenda_html))

                mapa_html = mapa._repr_html_()
                # # mapa.save("mapa_com_legenda.html")

                with coluna1:
                    # folium_static(mapa, width=350, height=300)

                    st.write("""
                        <div style="text-align: center; color: #333333;">
                            <h1  style="font-size: 10px; margin: 0; padding: 0">Acumulado de chuva das ultimas 24h</h1>
                        </div>
                        """,
                        unsafe_allow_html=True)
                    st.components.v1.html(mapa_html, width=600, height=350)

                    url_sib = "https://cth.daee.sp.gov.br/sibh/chuva_agora"
                    st.write(f"""
                        <div style="color: black; line-height: 1;">
                            <p style="text-align: center; font-size: 10px; margin: 0; padding: 0;">Fonte: Chuva agora - <a href="{url_sib}" target="_blank"> SIBH</a></p>
                        </div>
                        """,
                    unsafe_allow_html=True) 
                    
                with coluna2:

                    st.write("""
                        <div style="text-align: center; color: #333333;">
                            <h1  style="font-size: 10px; margin: 0; padding: 0">Interpolação dos pluviômetros a partir do método IDW</h1>
                        </div>
                        """,
                    unsafe_allow_html=True)
                    
                    # folium_static(mapa, width=500, height=320)
                    # st.markdown(legenda_html, unsafe_allow_html=True)
                    sp_border = gpd.read_file('./data/DIV_MUN_SP_2021a.shp').to_crs(epsg=4326)
                    sp_border_shapefile = "results/sp_border.shp"
                    municipio_arquivo = 'cities_idw'
                    excluir_prefixos = ""

                    data_stats = gerar_mapa_chuva_shapefile(excluir_prefixos, sp_border, sp_border_shapefile, municipio_arquivo)
            
                    selected_bounds = [0, 1, 2, 5, 7, 10, 15, 20, 25, 30, 40, 50, 75, 100, 250]
                    cmap = [
                        "#D5FFFF", "#00D5FF", "#0080AA", "#0000B3",
                        "#80FF55", "#00CC7F", "#558000", "#005500", "#FFFF00",
                        "#FFCC00", "#FF9900", "#D55500", "#FFBBFF", "#FF2B80", "#8000AA"
                    ]

                    # Criar colormap usando branca (folium usa branca para colorbar)
                    color_scale = cmb.StepColormap(
                        colors=cmap,
                        index=selected_bounds,
                        vmin=min(selected_bounds),
                        vmax=max(selected_bounds),  
                        caption=None
                    )


                    latitude =  -22.8859
                    longitude = -48.4451

                    mapa = folium.Map(
                        location=[latitude, longitude],  # Centralizar no meio dos pontos
                        zoom_start=5.5,
                        tiles=None,
                        control_scale=False, 
                        zoomControl=False
                    )

                    folium.TileLayer(
                        tiles='https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
                        attr=' ',
                        name='OpenStreetMap',
                        overlay=False,
                        control=True, 
                    ).add_to(mapa)

                    mapa.options['attributionControl'] = False

                    folium.GeoJson(
                        data_stats.to_json(),
                        name="Precipitação",
                        # style_function=style_function,
                        style_function=lambda feature: {
                            "fillColor": color_scale(feature['properties'].get("mean_precipitation")) if feature['properties'].get("mean_precipitation") is not None else "#ffffff",
                            "color": "black",
                            "weight": 0.3,
                            "fillOpacity": 0.7 if feature['properties'].get("mean_precipitation") is not None else 0.0,
                        }
                        # tooltip=folium.GeoJsonTooltip(fields=[f"mean_precipitation"], aliases=["Precipitação (mm)"]),
                    ).add_to(mapa)

                    # HTML manual para legenda horizontal com todos os rótulos
                    legend_bar = "<div style='position: fixed; bottom: 10px; left: 50%; transform: translateX(-50%); z-index:9999; background:white; padding:5px; border-radius:5px; font-size:10px; box-shadow: 0 2px 6px rgba(0,0,0,0.3); width: 90%; max-width: 600px; height: 31px;'>"
                    legend_bar += "<b> </b><div style='display: flex;'>"

                    # Adiciona blocos coloridos
                    for i in range(len(selected_bounds)):
                        legend_bar += f"<div style='flex:1;'><div style='background:{cmap[i]}; width: 100%; height: 13px;'></div><div style='width: 100%;'>{selected_bounds[i]}</div></div>"
                    legend_bar += "</div></div>"

                    # Insere a legenda
                    legend_element = Element(legend_bar)

                    mapa.get_root().html.add_child(legend_element)

                    mapa_html = mapa._repr_html_()
                    st.components.v1.html(mapa_html, width=600, height=350)
                    st.write(f"""
                        <div style="color: black; line-height: 1;">
                            <p style="text-align: center; font-size: 10px; margin: 0; padding: 0;">Elaborado pela equipe técnica da Sala de Situação São Paulo (SSSP). Parâmetros: Potência=0.02, Suavização=0.02 e Raio=0.5.</p>
                        </div>
                        """,
                    unsafe_allow_html=True)
                    


                with colun2:
                       
                    if 'user_input_chuva_slide1' not in st.session_state:
                        st.session_state.user_input_chuva_slide1 = "Clique para editar"
                    
                    user_input = st.text_area("Relatos 24h", value=st.session_state.user_input_chuva_slide1, height=200, key="user_input_chuva_slide1")
                    
            
            else:
                st.error("Erro ao carregar os dados da API.")

            st.write(" ")
            st.write(" ")
            st.write(" ")
            st.write(" ")
            st.write(" ")
            st.write(" ")
            st.write(" ")
            st.write(" ")
            st.write(" ")
            st.write(" ")
            st.write(" ")
            st.write(" ")
            st.write(" ")
            st.write(" ")



async def slide2():
    print("Rodando 2 - ", datetime.now())
    with slide2_container:
        col1, col2, col3 = st.columns([1.2, 1.5, 0.15])

        with col1:
            st.write("""
                <div class="align-left-center">
                    <div style="color: black;">
                        <p style="font-size: 11px">Agência de Água do Estado de São Paulo</h1>
                    </div>
                </div>
                """,
                unsafe_allow_html=True)

        with col3:
            st.markdown('<div class="align-right">', unsafe_allow_html=True)
            st.image("spaguas.png", caption="", width=200)
            st.markdown('</div>', unsafe_allow_html=True)

        with col2:
            st.write("""
            <div style="color: black;">
                <h1  style="font-size: 16px;">Dados Pluviometria</h1>
            </div>
            """,
            unsafe_allow_html=True)


        coluna1, coluna2= st.columns([1.0, 0.8])
            
        query_cities = f"""SELECT c.name as city_name,
                    max(ac_diario) AS max_ac_diario,
                    avg(ac_diario) AS ac_diario,
                    avg(ac_mensal) AS ac_mensal,
                        CASE
                            WHEN EXTRACT(month FROM now())::integer = 1 THEN rc.h_jan
                            WHEN EXTRACT(month FROM now())::integer = 2 THEN rc.h_fev
                            WHEN EXTRACT(month FROM now())::integer = 3 THEN rc.h_mar
                            WHEN EXTRACT(month FROM now())::integer = 4 THEN rc.h_abr
                            WHEN EXTRACT(month FROM now())::integer = 5 THEN rc.h_mai
                            WHEN EXTRACT(month FROM now())::integer = 6 THEN rc.h_jun
                            WHEN EXTRACT(month FROM now())::integer = 7 THEN rc.h_jul
                            WHEN EXTRACT(month FROM now())::integer = 8 THEN rc.h_ago
                            WHEN EXTRACT(month FROM now())::integer = 9 THEN rc.h_set
                            WHEN EXTRACT(month FROM now())::integer = 10 THEN rc.h_out
                            WHEN EXTRACT(month FROM now())::integer = 11 THEN rc.h_nov
                            WHEN EXTRACT(month FROM now())::integer = 12 THEN rc.h_dez
                            ELSE '0'::numeric
                        END AS media_historica
                FROM public.station_rainfall_accum_month re
                    LEFT JOIN cities c ON c.id = re.city_id
                    LEFT JOIN avg_rainfall_cities rc ON rc.cod_ibge::text = c.cod_ibge::text
                WHERE disponibilidade_diaria > 80 AND disponibilidade_mensal > 60::numeric AND ac_diario IS NOT null and c.name!='Município não Existente ou Incorporado por Outro'
                GROUP BY city_name, media_historica
                ORDER BY (avg(ac_diario)) DESC LIMIT 10;"""

        tabela_df= execute_query(query_cities)

        # print(tabela_df)
        tabela_df['media_historica'] = pd.to_numeric(tabela_df['media_historica'], errors='coerce')
        tabela_df['media_historica'] = tabela_df['media_historica'].round(1)
        tabela_df['media_historica'] = tabela_df['media_historica'].apply(lambda x: f'{x:.1f}' if pd.notna(x) else '-')
        tabela_df = tabela_df.rename(columns={'city_name': 'Municípios', 'max_ac_diario': 'Chuva Máximo (mm)', 'ac_diario': 'Chuva Média (mm)', 'ac_mensal':'Acum. média mês (mm)' , 'media_historica':'Histórico mensal (mm)'})
        
        query_ugrhis = f"""
                        SELECT INITCAP(u.name) as ugrhi_name,
                            avg(ac_diario) AS ac_diario
                        FROM public.station_rainfall_accum_month sr
                            left join stations s on s.id = sr.ugrhi_id
                            LEFT JOIN ugrhis u ON u.id = s.id
                        WHERE disponibilidade_diaria > 80 AND ac_diario IS NOT null AND u.name != 'FORA DO ESTADO DE SÃO PAULO'
                        GROUP BY ugrhi_name
                        ORDER BY (ac_diario) DESC;"""
            
        tabela_ugrhis_df= execute_query(query_ugrhis)

        with coluna1:

            styled_df = tabela_df.style\
            .format({
                    'Chuva Máximo (mm)': '{:.0f}', 
                    'Chuva Média (mm)': '{:.0f}', 
                    'Acum. média mês (mm)': '{:.0f}' 
                    })\
            .hide(axis="index")\
            .set_caption("Municípios com os maiores acumulados de chuvas observadas nas últimas 24h (mm) (Rede Telemétrica)")\
            .set_table_styles([
                {"selector": "caption", "props": [
                    ("color", "black"),
                    ("font-size", "14px"),
                    ("font-weight", "bold"),
                    ("text-align", "center"),
                    ("padding", "5px"),
                    ("caption-side", "top") 
                ]},
                {"selector": "th", "props": [
                    ("font-size", "14px"), 
                    ("background-color", "#f0f0f0"),
                    ("color", "#333333"),
                    ("padding", "5px"),
                    ("text-align", "center")
                    ]},
                {"selector": "td", "props": [
                    ("font-size", "14px"),
                    ("height", "7px"),
                    ("color", "#333333"),
                    ("padding", "2px 4px"),
                    ("text-align", "center"),
                    ("width", "100px")
                    # ("border-bottom", "1px solid #e0e0e0")
                    ]},
                {"selector": "tr:hover", "props": [(
                    "background-color", "#ffff99"),
                    ("cursor", "pointer")
                    ]}
            ])\
            .set_properties(**{"background-color": "#f9f9f9", "color": "#333333"})

            st.markdown(styled_df.to_html(), unsafe_allow_html=True)

            st.write("""
                    <div class="align-left-center">
                        <div style="color: black; line-height: 1;">
                            <p style="font-size: 12px; margin: 0.5; padding: 0;">1- Máximo Registrado - Volume máximo (mm) registrado por um posto pluviométrico do município.</p>
                            <p style="font-size: 12px; margin: 0.5; padding: 0;">2- Média Registrada - Soma do Volume (mm) de todos postos do municípios / n°postos.</p>
                            <p style="font-size: 12px; margin: 0.5; padding: 0;">3- Acumulado média mês - Soma da média (mm) registrada do primeiro dia do mês até o momento.</p>
                            <p style="font-size: 12px; margin: 0.5; padding: 0;">4- Histórico mensal - Volume médio mensal calculado a partir da série histórica disponível</p>
                        </div>
                    </div>
                """,
                unsafe_allow_html=True)
        
        tabela_df['Histórico mensal (mm)'] = tabela_df['Histórico mensal (mm)'].replace('-', 0)



        with coluna2:
            for col in ['Chuva Média (mm)', 'Chuva Máximo (mm)', 'Acum. média mês (mm)', 'Histórico mensal (mm)']:
                tabela_df[col] = tabela_df[col].astype(float)
        
        
            fig, ax = plt.subplots(figsize=(7, 5)) 

            # Configurações das barras
            n = len(tabela_df)  # Número de municípios
            largura_barra = 0.15  # Largura de cada barra individual
            espacamento = 0.05  # Espaço entre grupos de barras
            indice = np.arange(n)  # Posições no eixo X

            # Offset calculado corretamente
            offset = np.array([-1.5, -0.5, 0.5, 1.5]) * (largura_barra + espacamento/2)
            cores = ['#4CAF50', '#2196F3', '#FF5722', '#FFC107']

            # Plotagem das barras
            for i, (coluna, cor) in enumerate(zip(
                ['Chuva Média (mm)', 'Chuva Máximo (mm)', 'Acum. média mês (mm)', 'Histórico mensal (mm)'],
                cores
            )):
                ax.bar(
                    indice + offset[i],
                    tabela_df[coluna],
                    largura_barra,
                    color=cor,
                    alpha=0.8,
                    label=coluna
                )

            # Personalização do gráfico
            ax.set_title('Comparação de Precipitação por Município', fontsize=10, pad=30)
            ax.set_xlabel('Municípios', fontsize=6)
            ax.set_ylabel('Precipitação (mm)', fontsize=6)
            ax.set_xticks(indice)
            ax.set_xticklabels(tabela_df['Municípios'], rotation=45, ha='right', fontsize=7)
            ax.grid(axis='y', linestyle=':', alpha=0.3)
            
            # Ajuste do eixo Y
            max_valor = tabela_df[['Chuva Média (mm)', 'Chuva Máximo (mm)', 
                                'Acum. média mês (mm)', 'Histórico mensal (mm)']].max().max()
            ax.set_ylim(0, max_valor * 1.2)

            # Legenda fora do gráfico
            ax.legend(
                frameon=True,
                facecolor='#f0f0f0',
                fontsize=7,
                bbox_to_anchor=(0.5, 1.1),  # (posição horizontal, posição vertical)
                loc='upper center',  # Âncora no centro superior
                ncol=4  # Número de colunas para distribuir os itens
            )
            plt.tight_layout()
            st.pyplot(fig)

        with coluna2:
            fig, ax = plt.subplots(figsize=(6, 4))
            # Definindo as posições das barras
            n = len(tabela_ugrhis_df)
            indice = np.arange(n)  # Posições no eixo X (0, 1, 2, ...)

            # Largura das barras
            largura_barra = 0.5

            # Plotando as barras
            ax.bar(
                indice,                     # Eixo X: posições baseadas em 'ugrhi_name'
                tabela_ugrhis_df['ac_diario'],     # Eixo Y: valores de 'ac_diario'
                largura_barra,              # Largura da barra
                color='#2196F3',            # Cor da barra
                alpha=0.8,                  # Transparência
                label='AC Diário'           # Legenda
            )

            ax.set_title('Chuva média acumulada por UGRHI', fontsize=10)             # Título do gráfico
            ax.set_xticks(indice)                           # Define os ticks no eixo X
            ax.set_xticklabels(tabela_ugrhis_df['ugrhi_name'], fontsize=7)     # Nomes das UGRHIs nos ticks
            ax.set_ylabel('Precipitação (mm)', fontsize=8)

            # y_ticks = np.arange(0, max(tabela_ugrhis_df['ac_diario']) + 1, 0.5)  # Define os valores dos ticks
            # ax.set_yticks(y_ticks)  # Define os ticks no eixo Y


            # Rotaciona os rótulos do eixo X para melhor visualização (opcional)
            plt.xticks(rotation=45, ha='right')

            plt.tight_layout()
            st.pyplot(fig)

        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")


async def slide3():
    print('Rodando 3')
    with slide3_container:
        col1, col2, col3 = st.columns([1.2, 1.5, 0.15])

        with col1:
            st.write("""
                <div class="align-left-center">
                    <div style="color: black;">
                        <p style="font-size: 11px">Agência de Água do Estado de São Paulo</h1>
                    </div>
                </div>
                """,
                unsafe_allow_html=True)

        with col3:
            st.markdown('<div class="align-right">', unsafe_allow_html=True)
            st.image("spaguas.png", caption="", width=200)
            st.markdown('</div>', unsafe_allow_html=True)

        with col2:
            st.write("""
            <div style="color: black;">
                <h1  style="font-size: 16px;">Acumulados dos Radares</h1>
            </div>
            """,
            unsafe_allow_html=True)

        coluna1, coluna2= st.columns([1.2, 0.8])   
        
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')  # Modo sem interface gráfica
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size={},{}".format(1300, 2000)) #largura, altura
        options.add_argument("--disable-web-security")  # Desabilitar CORS
        service = Service(ChromeDriverManager().install(), port=62108)
        driver = webdriver.Chrome(options=options, service=service)

        usuario = os.environ.get('IPMET_USERNAME')
        senha = os.environ.get('IPMET_PASSWORD')

        url_ipmet = f"https://www.ipmetradar.com.br/restrito/2login.php?username={usuario}&senha={senha}&tipo_acesso=ip"
        # Navegar para a URL
        driver.get(url_ipmet)

        # Esperar o botão carregar e clicar nele
        driver.implicitly_wait(5)  # Espera até 5 segundos
        iframe = driver.find_element(By.TAG_NAME, "iframe")
        driver.switch_to.frame(iframe)

        driver.implicitly_wait(5)

        select_element = driver.find_element(By.CSS_SELECTOR, "#layer-select")
        select_element.click()
        tm.sleep(3)
        select = Select(select_element)
        select.select_by_value("acum24h")

        # Espera o conteúdo carregar
        tm.sleep(7)
        select_element.click()
        # Tirar a captura de tela
        driver.save_screenshot("screenshot.png")

        # Exibir a imagem
        img = Image.open("screenshot.png")
        imagem_recortada = img.crop((120, 362, 1100, 855)) #esquerda, cima, direita, baixo

        with coluna1:
            st.write("""
            <div style="text-align: center; color: #333333;">
                <h1  style="font-size: 10px; margin: 0; padding: 0">Acumulado das 24h (mm) - Radar Ipmet</h1>
            </div>
            """,
            unsafe_allow_html=True)
            st.image(imagem_recortada, caption="", use_container_width=True)

            st.write(f"""
                    <div style="color: black; line-height: 1;">
                        <p style="text-align: center; font-size: 10px; margin: 0; padding: 0;">Produzido pelo Ipmet. Disponível em: <a href="{url_ipmet}" target="_blank"> IPMET</a></p>
                    </div>
                """,
            unsafe_allow_html=True)

            if 'user_input' not in st.session_state:
                st.session_state.user_input = "Clique para editar"
            
            user_input = st.text_area("Análise", value=st.session_state.user_input, height=100)
            
            if user_input != st.session_state.user_input:
                st.session_state.user_input = user_input

        data_anterior = datetime.today() - timedelta(days=1)
        data_anterior_str = data_anterior.strftime('%d-%m-%Y').replace('-', '/')
        data = data_anterior.strftime('%Y%m%d')

        usuario = os.environ.get('SAISP_USERNAME')
        senha = os.environ.get('SAISP_PASSWORD')
            
        password_encoded = urllib.parse.quote(senha)
        print(f"https://{usuario}:{password_encoded}@www.saisp.br/geral/processo.jsp?comboFiltroGrupo=&PRODUTO=636&OVLCODE=EPI&dataInicial={data_anterior_str}+07%3A00&WHICHCODE=0&autoUpdate=1&STEP=&DI={data}0700&DF=")
        
    
        driver.get(f"https://{usuario}:{password_encoded}@www.saisp.br/geral/processo.jsp?comboFiltroGrupo=&PRODUTO=636&OVLCODE=EPI&dataInicial={data_anterior_str}+07%3A00&WHICHCODE=0&autoUpdate=1&STEP=&DI={data}0700&DF=")
        
        driver.implicitly_wait(30)
        driver.save_screenshot("screenshot_2.png")
        img_saisp = Image.open("screenshot_2.png")

        imagem_recortada_saisp = img_saisp.crop((492, 51, 972, 530)) #esquerda, cima, direita, baixo
        largura_borda = 2  # Largura da borda
        imagem_com_borda = ImageOps.expand(imagem_recortada_saisp, border=largura_borda, fill='black')  # Você pode mudar a cor da borda
        legenda = Image.open("imagens/Imagem1.jpg")

        st.markdown(
            """
            <style>
                .streamlit-expanderHeader {
                    border-radius: 0px !important;
                }
                img {
                    border-radius: 0px !important;
                }
            </style>
            """, unsafe_allow_html=True
        )

        with coluna2:
            st.write("""
            <div style="text-align: center; color: #333333;">
                <h1  style="font-size: 10px; margin: 0; padding: 0"> Acumulado das 24h (mm) - Radar SP Águas</h1>
            </div>
            """,
            unsafe_allow_html=True)
            st.image(imagem_com_borda, caption="", use_container_width=True) 
            st.image(legenda, caption="", use_container_width=True)
            url = "http://www.saisp.br"

            st.write(f"""
                    <div style="color: black; line-height: 1;">
                        <p style="text-align: center; font-size: 10px; margin: 0; padding: 0;">Produzido pelo Radar 600S-Selex, Banda S, 850 KW, Doppler, Dupla Polarização. Disponível em: <a href="{url}" target="_blank"> SAISP</a></p>
                    </div>
                """,
            unsafe_allow_html=True)


        # Fechar o navegador
        driver.quit()
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")

        # await asyncio.sleep(2)

async def slide4():
    with slide4_container:
    
        col1, col2, col3 = st.columns([0.9, 2.0, 0.15])

        with col1:
            st.write("""
                <div class="align-left-center">
                    <div style="color: black;">
                        <p style="font-size: 11px">Agência de Água do Estado de São Paulo</h1>
                    </div>
                </div>
                """,
                    unsafe_allow_html=True)

        with col3:
            st.markdown('<div class="align-right">', unsafe_allow_html=True)
            st.image("spaguas.png", caption="", width=300)
            st.markdown('</div>', unsafe_allow_html=True)

        with col2:
            st.write("""
            <div style="color: black;">
                <h1  style="font-size: 16px;">Mapa de precipitação pluviométrica das últimas 24 horas</h1>
            </div>
            """,
            unsafe_allow_html=True)

            st.write("""
                <div style="color: black">
                        <p style="font-size: 12px">Interpolação dos pluviômetros a partir do método IDW (cálculo de precipitação média)</h1>
                </div>
                """,
                    unsafe_allow_html=True)
            
            st.markdown('</div>', unsafe_allow_html=True)

            sp_border = gpd.read_file('./data/DIV_MUN_SP_2021a.shp').to_crs(epsg=4326)
            sp_border_shapefile = "results/sp_border.shp"
            municipio_arquivo = 'cities_idw'
            excluir_prefixos = ""

        colun1, colun2, colun3 = st.columns([0.3, 2.0, 0.3])
        with colun2:
            data_stats = gerar_mapa_chuva_shapefile(excluir_prefixos, sp_border, sp_border_shapefile, municipio_arquivo)
            
            selected_bounds = [0, 1, 2, 5, 7, 10, 15, 20, 25, 30, 40, 50, 75, 100, 250]
            cmap = [
                "#D5FFFF", "#00D5FF", "#0080AA", "#0000B3",
                "#80FF55", "#00CC7F", "#558000", "#005500", "#FFFF00",
                "#FFCC00", "#FF9900", "#D55500", "#FFBBFF", "#FF2B80", "#8000AA"
            ]

            # Criar colormap usando branca (folium usa branca para colorbar)
            color_scale = cmb.StepColormap(
                colors=cmap,
                index=selected_bounds,
                vmin=min(selected_bounds),
                vmax=max(selected_bounds),  
                caption=None
            )

            legend_html = color_scale._repr_html_()

            map_center = data_stats.geometry.unary_union.centroid.coords[:][0][::-1]  # (lat, lon)

            mapa = folium.Map(
                location=map_center,  # Centralizar no meio dos pontos
                zoom_start=5.5,
                tiles=None,
                control_scale=False, 
                zoomControl=False
            )

            folium.TileLayer(
                tiles='https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
                attr=' ',
                name='OpenStreetMap',
                overlay=False,
                control=True, 
            ).add_to(mapa)

            mapa.options['attributionControl'] = False

            folium.GeoJson(
                data_stats.to_json(),
                name="Precipitação",
                # style_function=style_function,
                style_function=lambda feature: {
                    "fillColor": color_scale(feature['properties'].get("mean_precipitation")) if feature['properties'].get("mean_precipitation") is not None else "#ffffff",
                    "color": "black",
                    "weight": 0.3,
                    "fillOpacity": 0.7 if feature['properties'].get("mean_precipitation") is not None else 0.0,
                }
                # tooltip=folium.GeoJsonTooltip(fields=[f"mean_precipitation"], aliases=["Precipitação (mm)"]),
            ).add_to(mapa)

            # HTML manual para legenda horizontal com todos os rótulos
            legend_bar = "<div style='position: fixed; bottom: 10px; left: 50%; transform: translateX(-50%); z-index:9999; background:white; padding:5px; border-radius:5px; font-size:12px; box-shadow: 0 2px 6px rgba(0,0,0,0.3); width: 90%; max-width: 600px;'>"
            legend_bar += "<b> </b><div style='display: flex;'>"

            # Adiciona blocos coloridos
            for i in range(len(selected_bounds)):
                legend_bar += f"<div style='flex:1;'><div style='background:{cmap[i]}; width: 100%; height: 15px;'></div><div style='width: 100%;'>{selected_bounds[i]}</div></div>"
            legend_bar += "</div></div>"

            # Adiciona os rótulos uniformemente distribuídos
            # legend_bar += "<div style='display: flex; justify-content: space-between;'>"
            # for b in selected_bounds:
            #     legend_bar += f"<span>{b}</span>"
            # legend_bar += "</div></div>"

            # Insere a legenda
            legend_element = Element(legend_bar)

            mapa.get_root().html.add_child(legend_element)

            mapa_html = mapa._repr_html_()
            st.components.v1.html(mapa_html, width=700, height=600)

        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        
        # await asyncio.sleep(3)

async def slide5():
    with slide5_container:
        col1, col2, col3 = st.columns([1.2, 1.5, 0.15])

        with col1:
            st.write("""
                <div class="align-left-center">
                    <div style="color: black;">
                        <p style="font-size: 11px">Agência de Água do Estado de São Paulo</h1>
                    </div>
                </div>
                """,
                    unsafe_allow_html=True)

        with col3:
            st.markdown('<div class="align-right">', unsafe_allow_html=True)
            st.image("spaguas.png", caption="", width=300)
            st.markdown('</div>', unsafe_allow_html=True)

        with col2:
            st.write("""
            <div style="color: black;">
                <h1  style="font-size: 16px;">Dados Fluviometria</h1>
            </div>
            """,
            unsafe_allow_html=True)


        c1, c2, c3 = st.columns([0.1, 1.2, 0.1])

        data_inicial = datetime.today()
        hora_inicial = time(10, 0)
        data_hora_inicial = datetime.combine(data_inicial, hora_inicial)
        data_inicial_str = data_hora_inicial.strftime('%Y-%m-%d %H:%M')

        data_final = datetime.today() - timedelta(days=1)
        hora_final = time(10, 0)
        data_hora_final = datetime.combine(data_final, hora_final)
        data_final_str = data_hora_final.strftime('%Y-%m-%d %H:%M')


        query = f"""with refs as (
                        select
                            rvl.*
                        from station_prefixes as sp
                        inner join reference_values_levels rvl on (rvl.station_prefix_id = sp.id)
                    ),
                    level_states as (
                    select
                        sp.id,
                        sp.prefix,
                        s.city_id,
                        s.ugrhi_id,
                        s."name",
                        s.latitude,
                        s.longitude,
                        m.date_hour,
                        m.value,
                        case when m.value >= refs.extravasation_level then 'Extravasamento'
                            when m.value >= refs.emergency_level then 'Emergência'
                            when m.value >= refs.alert_level then 'Alerta'
                            when m.value >= refs.attention_level then 'Atenção'
                            when m.value < refs.normal_level then 'Normal'
                            else 'Desconhecido' end as state,
                            refs.extravasation_level, refs.emergency_level, refs.alert_level, refs.attention_level, refs.normal_level
                    from measurements as m
                    left join station_prefixes as sp on (sp.id = m.station_prefix_id)
                    left join stations as s on (s.id = sp.station_id)
                    left join refs on (refs.station_prefix_id = sp.id)
                    where m.date_hour between '{data_final_str}' and '{data_inicial_str}' and sp.station_type_id  = 1 and m.value != 'NaN' and sp.public = true order by m.date_hour, sp.prefix),
                    current_state as (
                    select 
                        level_states."name" as station_name,
                        level_states.latitude,
                        level_states.longitude,
                        level_states.state,
                        level_states.city_id,
                        level_states.ugrhi_id,
                        level_states.id as station_prefix_id, 
                        level_states.prefix, 
                        level_states.value, 
                        level_states.date_hour,
                        LEAD(level_states.state, 1) OVER (PARTITION BY level_states.prefix) AS previous_state,
                        CASE 
                        WHEN LEAD(level_states.state, 1) OVER (PARTITION BY level_states.prefix) <> level_states.state THEN 
                            LEAD(level_states.date_hour, 1) OVER (PARTITION BY level_states.prefix)
                        ELSE NULL
                            END AS previous_data,
                        level_states.extravasation_level,
                        level_states.emergency_level, 
                        level_states.alert_level, 
                        level_states.attention_level, 
                        level_states.normal_level
                        FROM level_states)    
                    SELECT 
                        station_prefix_id, 
                        prefix, 
                        station_name,
                        c.name as municipio,
                        u.name as ugrhi,
                        value, 
                        state as current_state, 
                        date_hour as current_data,
                        previous_state,
                        previous_data,
                        CASE
                            WHEN state <> previous_state THEN 1
                            ELSE 0
                        END AS new_event, 
                        extravasation_level,
                        emergency_level, 
                        alert_level, 
                        attention_level, 
                        normal_level,
                        latitude,
                        longitude
                    FROM current_state
                    left join cities c on c.id= city_id
                    left join ugrhis u on u.id = ugrhi_id;"""
        
        df_extravasation= execute_query(query)

        print("Rodou a query -", datetime.now())
        df_extravasation['value'] = pd.to_numeric(df_extravasation['value'], errors='coerce')
        df_extravasation['latitude'] = pd.to_numeric(df_extravasation['latitude'], errors='coerce')
        df_extravasation['longitude'] = pd.to_numeric(df_extravasation['longitude'], errors='coerce')
        df_extravasation['station_prefix_id'] = df_extravasation['station_prefix_id'].astype(str)
        df_extravasation = df_extravasation.sort_values(by="value", ascending=True)

        df_max_values = df_extravasation.groupby('prefix', as_index=False).agg(
                            value=('value', 'max'),
                            latitude=('latitude', 'first'), 
                            longitude=('longitude', 'first'),
                            extravasation_level = ('extravasation_level','first'),
                            emergency_level=('emergency_level','first'),
                            alert_level =('alert_level', 'first'),
                            attention_level=('attention_level', 'first'), 
                            normal_level=('normal_level', 'first'),
                            station_name=('station_name', 'first')
                        ) 

        df_max_values['current_state'] = df_max_values.apply(classify_state, axis=1)
        df_max_values = df_max_values[df_max_values['current_state']!='Níveis Indefinidos']
        
        percentages = {
            'Extravasamento': len(df_max_values[df_max_values['current_state']=='Extravasamento']),
            'Emergência': len(df_max_values[df_max_values['current_state']=='Emergência']),
            'Alerta': len(df_max_values[df_max_values['current_state']=='Alerta']),
            'Atenção': len(df_max_values[df_max_values['current_state']=='Atenção']),
            'Normal': len(df_max_values[df_max_values['current_state']=='Normal'])
        }
        

        estados = ['Atenção', 'Alerta', 'Emergência', 'Extravasamento']

        # Separar extravasamento/emergência e outros
        dados_criticos = []  # Para Extravasamento e Emergência
        partes_porcentagens = []
        estado_sem_registro = []

        for estado in estados:
            if estado in df_max_values['current_state'].values and estado in ['Extravasamento', 'Emergência']:
                postos = df_max_values[df_max_values['current_state'] == estado]['station_name'].to_list()

                if postos:
                    postos = [p.title() for p in postos]
                    if len(postos) == 1:
                        prefixo = "no posto"
                        postos_str = postos[0]
                    else:
                        prefixo = "nos postos"
                        postos_str = ', '.join(postos[:-1]) + ' e ' + postos[-1]
                    
                    dados_criticos.append(f" {estado} {prefixo} {postos_str}")

                if percentages.get(estado, 0) <= 0:
                    estado_sem_registro.append(estado)

            else:
                if percentages.get(estado, 0) > 0:
                    partes_porcentagens.append(f"{percentages.get(estado, 0)} postos estão em nível de {estado}")
                else:
                    estado_sem_registro.append(estado)

        # Construindo a legenda
        legenda = "De acordo com as redes telemétricas públicas do Estado de São Paulo foram regitrados"

        # Primeiro Extravasamento/Emergência
        if dados_criticos:
            if len(dados_criticos) == 1:
                legenda += f" níveis em {dados_criticos[0]}, "
            else:
                legenda += f" níveis de {dados_criticos[0]} e {dados_criticos[1]}, "

        # Agora Normal + porcentagens
        normal_texto = f"{percentages.get('Normal', 0)} postos em nível normal"

        if partes_porcentagens:
            normal_texto += ", "

        legenda += normal_texto

        if partes_porcentagens:
            if len(partes_porcentagens) == 1:
                porcentagens_str = partes_porcentagens[0]
            else:
                porcentagens_str = ', '.join(partes_porcentagens[:-1]) + ' e ' + partes_porcentagens[-1]
            
            legenda += porcentagens_str + "."
        else:
            legenda += "."

        # E por fim estados sem registro
        if 'Extravasamento' in estado_sem_registro:
            
            legenda += f" Não ocorreram Extravasamentos durante o perído analisado."
        
        mapa = folium.Map(
            location=[-22.7832, -48.4430],  # Centralizar no meio dos pontos
            zoom_start=6.5,
            tiles=None,
            control_scale=False, 
            zoomControl=False
        )

        folium.TileLayer(
            tiles='https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
            attr=' ',
            name='OpenStreetMap',
            overlay=False,
            control=True
        ).add_to(mapa)

        mapa.options['attributionControl'] = False

        shapefile_path = "data/limiteestadualsp.shp"
        gdf = gpd.read_file(shapefile_path)

        folium.GeoJson(
            gdf,
            name='Shapefile',
            style_function=lambda x: {
                'fillColor': '#808080',  # Cor de preenchimento
                'color': 'black',     # Cor da borda
                'weight': 0.5,          # Espessura da borda
                'fillOpacity': 0.2    # Transparência do preenchimento
            }
        ).add_to(mapa)

        normal_layer = folium.FeatureGroup(name='Normal')
        atencao_layer = folium.FeatureGroup(name='Atenção')
        alerta_layer = folium.FeatureGroup(name='Alerta')
        emergencia_layer = folium.FeatureGroup(name='Emergência')
        extravasamento_layer = folium.FeatureGroup(name='Extravasamento')

        # Adicionar marcadores para cada ponto
        for index, row in df_max_values.iterrows():
            lat = row['latitude']
            lon = row['longitude']
            valor = row['value']
            state = row['current_state']

            valor_inteiro = int(valor)
            popup = f"Valor: {valor}"
            
            valor_inteiro = int(valor)

            if valor_inteiro>0:
                # Criar um popup com o valor
                popup = f"Valor: {valor}"

                if state == 'Extravasamento':
                    folium.CircleMarker(
                        location=[lat, lon],
                        radius=4,  # Tamanho do marcador
                        color="black",  # Borda branca
                        weight=0.3,  # Espessura da borda
                        fill=True,
                        fill_color="#f74f78",
                        fill_opacity=1.0,
                        popup=popup
                    ).add_to(extravasamento_layer)

                elif state == 'Emergência':
                    folium.CircleMarker(
                        location=[lat, lon],
                        radius=4,  # Tamanho do marcador
                        color="black",  # Borda branca
                        weight=0.3,  # Espessura da borda
                        fill=True,
                        fill_color='#cc00ff',
                        fill_opacity=1.0,
                        popup=popup
                    ).add_to(emergencia_layer)

                elif state == 'Alerta':
                    folium.CircleMarker(
                        location=[lat, lon],
                        radius=4,  # Tamanho do marcador
                        color="black",  # Borda branca
                        weight=0.3,  # Espessura da borda
                        fill=True,
                        fill_color='#ffb15c',
                        fill_opacity=1.0,
                        popup=popup
                    ).add_to(alerta_layer)

                elif state == 'Atenção':
                    folium.CircleMarker(
                        location=[lat, lon],
                        radius=4,  # Tamanho do marcador
                        color="black",  # Borda branca
                        weight=0.3,  # Espessura da borda
                        fill=True,
                        fill_color='#bda501',
                        fill_opacity=1.0,
                        popup=popup
                    ).add_to(atencao_layer)

                else: 
                    folium.CircleMarker(
                        location=[lat, lon],
                        radius=4,  # Tamanho do marcador
                        color="black",  # Borda branca
                        weight=0.3,  # Espessura da borda
                        fill=True,
                        fill_color='#16c995',
                        fill_opacity=1.0,
                        popup=popup
                    ).add_to(normal_layer)

        normal_layer.add_to(mapa)
        atencao_layer.add_to(mapa)
        alerta_layer.add_to(mapa)
        emergencia_layer.add_to(mapa)
        extravasamento_layer.add_to(mapa)

        folium.LayerControl().add_to(mapa)
        
        legenda_html = """
        <div style="position: fixed; z-index:999999; bottom: 22px; left: 50%; transform: translateX(-50%); background: white; padding: 2px; border-radius: 5px; box-shadow: 0 0 3px rgba(0,0,0,0.3); display: flex; align-items: center; justify-content: center;">
            <div style="display: flex; align-items: center; margin-right: 5px;">
                <div style="width: 60px; height: 15px; background-color: #16c995; display: flex; align-items: center; justify-content: center; color: white; font-size: 8px; border-radius: 3px;">
                    <span> Normal</span>
                </div>
            </div>
            <div style="display: flex; align-items: center; margin-right: 5px;">
                <div style="width: 60px; height: 15px; background-color: #bda501; display: flex; align-items: center; justify-content: center; color: white; font-size: 8px; border-radius: 3px;">
                    <span> Atenção</span>
                </div>   
            </div>
            <div style="display: flex; align-items: center; margin-right: 5px;">
                <div style="width: 60px; height: 15px; background-color: #ffb15c; display: flex; align-items: center; justify-content: center; color: white; font-size: 8px; border-radius: 3px;">
                    <span> Alerta </span>
                </div>
            </div>
            <div style="display: flex; align-items: center; margin-right: 5px;">
                <div style="width: 60px; height: 15px; background-color: #cc00ff; display: flex; align-items: center; justify-content: center; color: white; font-size: 8px; border-radius: 3px;">
                    <span> Emergência </span>
                </div>
            </div>
            <div style="display: flex; align-items: center;">
                <div style="width: 60px; height: 15px; background-color: #f74f78; display: flex; align-items: center; justify-content: center; color: white; font-size: 8px; border-radius: 3px;">
                    <span> Extravasamento </span>
                </div>
            </div>
        </div>
        """

        mapa.get_root().html.add_child(Element(legenda_html))

        mapa_html = mapa._repr_html_()
        # mapa.save("mapa_com_legenda.html")

        with c2:
            # folium_static(mapa, width=600, height=400)
            st.components.v1.html(mapa_html, width=1000, height=580)

            url_sib = "https://cth.daee.sp.gov.br/sibh/chuva_agora"
            st.write(f"""
                    <div style="color: black; line-height: 1;">
                        <p style="text-align: center; font-size: 12px; margin: 0; padding: 0;">Fonte: Chuva agora - <a href="{url_sib}" target="_blank"> SIBH</a></p>
                    </div>
                    """,
                unsafe_allow_html=True)
            
            if 'user_input_slide5' not in st.session_state:
                st.session_state.user_input_slide5 = legenda  # sem f-string desnecessária

            st.text_area("Análise das redes Telemétrica", height=100, key="user_input_slide5")
            
            st.write(" ")
            st.write(" ")
            st.write(" ")
            st.write(" ")
            st.write(" ")
            st.write(" ")

            

        if 'Extravasamento' in df_extravasation['current_state'].values:
            get_prefix = df_extravasation[df_extravasation['current_state']=='Extravasamento']


            prefix_id = get_prefix['station_prefix_id'].unique()

            df_extravasation = df_extravasation[df_extravasation['station_prefix_id'].isin(prefix_id)]


            for station_prefix_id in prefix_id:  # Iterando sobre os IDs já conhecidos
                df_filtered = df_extravasation[df_extravasation['station_prefix_id'].astype(str) == station_prefix_id]

                df_filtered = df_filtered.sort_values(by='current_data', ascending=True)

                count_extravasation = len(df_filtered[df_filtered['current_state']=='Extravasamento'])
                count_emergency = len(df_filtered[df_filtered['current_state']=='Emergência'])
                count_alert = len(df_filtered[df_filtered['current_state']=='Alerta'])
                count_attention = len(df_filtered[df_filtered['current_state']=='Atenção'])
                count_normal = len(df_filtered[df_filtered['current_state']=='Normal'])

                total_count = len(df_filtered)
                
                percentages = {
                    'Extravasamento': (count_extravasation / total_count) * 100 if total_count > 0 else 0,
                    'Emergência': (count_emergency / total_count) * 100 if total_count > 0 else 0,
                    'Alerta': (count_alert / total_count) * 100 if total_count > 0 else 0,
                    'Atenção': (count_attention / total_count) * 100 if total_count > 0 else 0,
                    'Normal': (count_normal / total_count) * 100 if total_count > 0 else 0
                }
                

                col1, col2, col3 = st.columns([1.2, 1.5, 0.15])
                
                id_station = df_filtered['prefix'].iloc[0]
                name_station = df_filtered['station_name'].iloc[0]

                with col1:
                    st.write("""
                        <div class="align-left-center">
                            <div style="color: black;">
                                <p style="font-size: 11px">Agência de Água do Estado de São Paulo</h1>
                            </div>
                        </div>
                        """,
                            unsafe_allow_html=True)

                with col3:
                    st.markdown('<div class="align-right">', unsafe_allow_html=True)
                    st.image("spaguas.png", caption="", width=300)
                    st.markdown('</div>', unsafe_allow_html=True)

                with col2:
                    st.write("""
                    <div style="color: black;">
                        <h1  style="font-size: 16px;">Gráfico do Extravasamento</h1>
                    </div>
                    """,
                    unsafe_allow_html=True)

                   

                cols = st.columns(5)

                background_colors = {
                    'Extravasamento': '#da070f',  # Vermelho
                    'Emergência': '#8435b7',      # Roxo
                    'Alerta': '#f95108',          # Laranja
                    'Atenção': '#f8d202',         # Amarelo
                    'Normal': '#268b12'           # Verde
                }

                with cols[0]:
                    st.markdown(f"""
                    <div style="background-color:#da070f; padding: 7px; border-radius: 3px; height: auto; display:flex; flex-direction: column; align-items: center; justify-content: center">
                        <div style="color: white; text-align: center; font-size: 14px;"><strong>Extravasamento</strong></div>
                        <div style="color: white; text-align: center; font-size: 12px;">{percentages['Extravasamento']:.2f}%</div>
                    </div>
                    """, unsafe_allow_html=True)

                with cols[1]:
                    st.markdown(f"""
                    <div style="background-color:#8435b7; padding: 7px; border-radius: 3px; height: auto; display:flex; flex-direction: column; align-items: center; justify-content: center">
                        <div style="color: white; text-align: center; font-size: 14px;"><strong>Emergência</strong></div>
                        <div style="color: white; text-align: center; font-size: 12px;">{percentages['Emergência']:.2f}%</div>
                    </div>
                    """, unsafe_allow_html=True)

                with cols[2]:
                    st.markdown(f"""
                    <div style="background-color:#f95108; padding: 7px; border-radius: 3px; height: auto; display:flex; flex-direction: column; align-items: center; justify-content: center">
                        <div style="color: white; text-align: center; font-size: 14px;"><strong>Alerta</strong></div>
                        <div style="color: white; text-align:: center; font-size: 12px;">{percentages['Alerta']:.2f}%</div>
                    </div>
                    """, unsafe_allow_html=True)

                with cols[3]:
                    st.markdown(f"""
                    <div style="background-color:#f8d202; padding: 7px; border-radius: 3px; height: auto; display:flex; flex-direction: column; align-items: center; justify-content: center">
                        <div style="color: white; text-align: center; font-size: 14px;"><strong>Atenção</strong></div>
                        <div style="color: white; text-align: center; font-size: 12px;">{percentages['Atenção']:.2f}%</div>
                    </div>
                    """, unsafe_allow_html=True)

                with cols[4]:
                    st.markdown(f"""
                    <div style="background-color:#268b12; padding: 7px; border-radius: 3px; height: auto; display:flex; flex-direction: column; align-items: center; justify-content: center">
                        <div style="color: white; text-align: center; font-size: 14px;"><strong>Normal</strong></div>
                        <div style="color: white; text-align: center; font-size: 12px;">{percentages['Normal']:.2f}%</div>
                    </div>
                    """, unsafe_allow_html=True)

                fig = go.Figure()

                fig.add_trace(go.Scatter(x=df_filtered['current_data'], y=df_filtered['value'], mode='lines', name='Valor', line=dict(color='#268b12', width=1), line_shape='spline'))

                # Adicionando as linhas horizontais para os níveis
                if not df_filtered['extravasation_level'].isnull().all():
                    fig.add_trace(go.Scatter(x=df_filtered['current_data'], y=df_filtered['extravasation_level'], 
                                            mode='lines', name='Extravasamento', line=dict(dash='dash', color='#da070f', width=1)))
                    
                if not df_filtered['emergency_level'].isnull().all():
                    fig.add_trace(go.Scatter(x=df_filtered['current_data'], y=df_filtered['emergency_level'], 
                                            mode='lines', name='Emergência', line=dict(dash='dash', color='#8435b7', width=1)))

                if not df_filtered['alert_level'].isnull().all():
                    fig.add_trace(go.Scatter(x=df_filtered['current_data'], y=df_filtered['alert_level'], 
                                            mode='lines', name='Alerta', line=dict(dash='dash', color='#f95108', width=1)))

                if not df_filtered['attention_level'].isnull().all():
                    fig.add_trace(go.Scatter(x=df_filtered['current_data'], y=df_filtered['attention_level'], 
                                            mode='lines', name='Atenção', line=dict(dash='dash', color='#f8d202', width=1)))
                

                # Atualizando o layout do gráfico
                fig.update_layout(
                    title=f"Dados fluviométricos do posto - {id_station} - {name_station}",
                    # title_x=0.3,
                    xaxis_title="Horas",
                    yaxis_title="Valor",
                    plot_bgcolor='white',    # Cor de fundo do gráfico
                    paper_bgcolor='white',   # Cor de fundo da área ao redor do gráfico
                    font=dict(color='black'),  # Cor das fontes para preto
                    title_font=dict(color='black'),  # Cor do título
                    xaxis_title_font=dict(color='black'),  # Cor do título do eixo X
                    yaxis_title_font=dict(color='black'), 
                    legend=dict(font=dict(color='black')),
                    xaxis=dict(tickfont=dict(color='black', size=9), gridcolor='lightgray', dtick="3600000", tickformat="%H:%M"),# Cor dos valores no eixo X
                    yaxis=dict(tickfont=dict(color='black', size=9), gridcolor='lightgray', tickformat=".", tickmode='auto') 
                )

                # Exibindo o gráfico no Streamlit
                st.plotly_chart(fig)

                
                
                df_extravasamento = df_filtered[df_filtered['current_state'] == 'Extravasamento']
                first_extravasamento_date = df_extravasamento['current_data'].min()
                last_extravasamento_date = df_extravasamento['current_data'].max()

                atual_state = df_filtered['current_state'].iloc[-1]
                nivel_atual = round(df_filtered['value'].iloc[-1], 3)
                nivel_max = round(df_filtered['value'].max(), 3)
                minucipio = df_filtered['municipio'].iloc[0]
                ugrhi = df_filtered['ugrhi'].iloc[0]
                
                if first_extravasamento_date == last_extravasamento_date:
                    duracao = timedelta(minutes=10)  # Duração padrão de 10 minutos
                else:
                    # Calculando a duração correta
                    duracao = last_extravasamento_date - first_extravasamento_date

                duracao= str(duracao).replace("days", "dias")
                
                summary_data = {
                    'Posto':[name_station],
                    'Município':[minucipio],
                    'UGRHI':[ugrhi],
                    'Início do extravasamento': [first_extravasamento_date],
                    'Fim do extravasamento': [last_extravasamento_date],
                    'Duração':[duracao],
                    'FLU (m) cota': [round(nivel_atual, 3)],
                    'Nível máximo':[round(nivel_max, 3)],
                    'Estado Atual': [atual_state]
                }

                summary_df = pd.DataFrame(summary_data).reset_index(drop=True)

                
                styled_df = summary_df.reset_index(drop=True).style \
                    .set_table_styles([
                        {'selector': 'table',
                        'props': [
                            ('background-color', 'white'),
                            ('width', '100%'),  # Adicionar largura total
                            ('table-layout', 'fixed')  # Isso força o uso das larguras definidas
                        ]}, 
                        # Estilo para o cabeçalho
                        {'selector': 'thead th', 
                        'props': [('background-color', 'lightgray'), 
                                ('color', '#2E2E2E'), 
                                ('font-weight', 'bold'),
                                ('text-align', 'center'),
                                ('font-size', '14px'),
                                ("padding", "5px 5px"),
                                ('height', '40px'),
                                ('max-height', '40px'),
                                ('min-height', '40px')]},
                                                                
                        # Estilo para as linhas horizontais (linhas da tabela)
                        {'selector': 'tbody tr', 
                        'props': [('border-bottom', '1px solid #d3d3d3'), 
                                ('height', '35px'),
                                ('max-height', '35px'),
                                ('min-height', '35px')]},

                        # Estilo para as células
                        {'selector': 'td', 
                        'props': [('padding', '10px'),
                                ('color', '#2E2E2E'), 
                                ('text-align', 'center'),
                                ('vertical-align', 'middle'),
                                ('font-size', '12px'),
                                ('border-left', 'none'),
                                ('border-right', 'none'),
                                ('overflow', 'hidden'),  # Importante para conteúdo longo
                                ('text-overflow', 'ellipsis'),  # Adiciona "..." se texto for muito longo
                                ('white-space', 'nowrap')]},

                        {"selector": "th.col0", "props": [("width", "200px")]},
                        {"selector": "td.col0", "props": [("width", "200px")]},
                        {"selector": "th.col1", "props": [("width", "130px")]},
                        {"selector": "td.col1", "props": [("width", "130px")]},
                        {"selector": "th.col2", "props": [("width", "100px")]},
                        {"selector": "td.col2", "props": [("width", "100px")]},
                        {"selector": "th.col3", "props": [("width", "190px")]},
                        {"selector": "td.col3", "props": [("width", "190px")]},
                        {"selector": "th.col4", "props": [("width", "190px")]},
                        {"selector": "td.col4", "props": [("width", "190px")]},
                        {"selector": "th.col5", "props": [("width", "100px")]},
                        {"selector": "td.col5", "props": [("width", "100px")]},
                        {"selector": "th.col6", "props": [("width", "100px")]},
                        {"selector": "td.col6", "props": [("width", "100px")]},
                        {"selector": "th.col7", "props": [("width", "100px")]},
                        {"selector": "td.col7", "props": [("width", "100px")]}
                    ]) \
                    .format({
                        'FLU (m) cota': '{:.2f}',  # Formatar para 2 casas decimais
                        'Nível máximo': '{:.2f}'    # Formatar para 2 casas decimais
                    }) \
                    .hide(axis="index") 

                
                st.markdown(styled_df.to_html(), unsafe_allow_html=True)
                # st.table(styled_df)
                # st.dataframe(styled_df, use_container_width=True)

                st.write(" ")
                st.write(" ")
                st.write(" ")
                st.write(" ")
                st.write(" ")
                st.write(" ")
                st.write(" ")
                st.write(" ")
                st.write(" ")
                st.write(" ")
                st.write(" ")
                st.write(" ")
                st.write(" ") 
                st.write(" ")
                st.write(" ")
                st.write(" ") 
                


async def slide6(): 
    with slide6_container:
        col1, col2, col3 = st.columns([1.2, 1.5, 0.15])

        with col1:
            st.write("""
                <div class="align-left-center">
                    <div style="color: black;">
                        <p style="font-size: 11px">Agência de Água do Estado de São Paulo</h1>
                    </div>
                </div>
                """,
                    unsafe_allow_html=True)

        with col3:
            st.markdown('<div class="align-right">', unsafe_allow_html=True)
            st.image("spaguas.png", caption="", width=300)
            st.markdown('</div>', unsafe_allow_html=True)

        with col2:
            st.write("""
            <div style="color: black;">
                <h1  style="font-size: 16px;">Sistema Produtores da RMSP</h1>
            </div>
            """,
            unsafe_allow_html=True)


        coluna1, coluna2, coluna3 = st.columns([0.2, 1.5, 0.2])

        data_atual = datetime.today()
        data_ano_anterior = datetime.today() - timedelta(days=365)
        data_atual_str = data_atual.strftime('%Y-%m-%d')
        data_ano_anterior_str = data_ano_anterior.strftime('%Y-%m-%d')

        url_ano_atual = f"https://mananciais-sabesp.fcth.br/api/Mananciais/Boletins/Mananciais/{data_atual_str}"
        response = requests.get(url_ano_atual, verify=False)

        if response.status_code == 200:

            data = response.json()

            if 'ReturnObj' in data and 'dadosSistemas' in data['ReturnObj']:
                df_sistemas_ano_atual = pd.DataFrame(data['ReturnObj']['dadosSistemas'])
            else:
                print("A chave 'dadosSistemas' não foi encontrada dentro de 'ReturnObj' ou 'ReturnObj' está vazio.")
        else:
            print(f"Erro na requisição ano atual. Status Code: {response.status_code}")

        url_ano_anteior = f"https://mananciais-sabesp.fcth.br/api/Mananciais/Boletins/Mananciais/{data_ano_anterior_str}"
        response = requests.get(url_ano_anteior, verify=False)

        if response.status_code == 200:

            data = response.json()

            if 'ReturnObj' in data and 'dadosSistemas' in data['ReturnObj']:
                df_sistemas_ano_anterior = pd.DataFrame(data['ReturnObj']['dadosSistemas'])
                ano_anterior = df_sistemas_ano_anterior[["SistemaId", "VolumePorcentagem"]]
                ano_anterior = ano_anterior.rename(columns={"VolumePorcentagem": "Volume Ano Anterior (%)"})
            else:
                print("A chave 'dadosSistemas' não foi encontrada dentro de 'ReturnObj' ou 'ReturnObj' está vazio.")
        else:
            print(f"Erro na requisição ano anterior. Status Code: {response.status_code}")

        merged_data = pd.merge(df_sistemas_ano_atual, ano_anterior, on='SistemaId', how='left')

        dados_sistema = {
            "Cantareira": 0,
            "Alto Tietê": 1,
            "Guarapiranga": 2,
            "Cotia": 3,
            "Rio Grande": 4, 
            "Rio Claro":5,
            "São Lourenço": 17,
        }

        df_sistemas = pd.DataFrame(list(dados_sistema.items()), columns=["Sistema", "SistemaId"])

        merged_data_sistemas = pd.merge(merged_data, df_sistemas, on='SistemaId', how='left')
        merged_data_sistemas = merged_data_sistemas.dropna(subset=['Sistema'])
        merged_data_sistemas['Diferença Vol. Anual (%)'] = merged_data_sistemas['VolumePorcentagem'] - merged_data_sistemas['Volume Ano Anterior (%)']

        merged_data_sistemas = merged_data_sistemas.rename(columns={'VolumePorcentagem': 'VolumeAtual (%)', 'Precipitacao': 'Chuva (mm)', 'PrecipitacaoAcumuladaNoMes': 'Acumulado no Mês (mm)', 'PMLTMensal':'Média Histórica (mm)'})

        merged_data_sistemas = merged_data_sistemas[['Sistema', 'VolumeAtual (%)', 'Volume Ano Anterior (%)', 'Diferença Vol. Anual (%)', 'Chuva (mm)', 'Acumulado no Mês (mm)', 'Média Histórica (mm)']]

        with coluna2:
            st.write("""
                <div style="text-align: center";"color: black">
                        <p style="font-size: 13px">Sistemas Produtores</h1>
                </div>
                """,
                    unsafe_allow_html=True)
            
            url = 'https://cth.daee.sp.gov.br/ssdsp/'
            imagem = capturar_tela(url)
            imagem_recortada = imagem.crop((90, 1000, 1450, 1800))

            st.image(imagem_recortada, caption="", use_container_width=True)

            st.markdown(f'<p style="text-align: center; font-size: 12px">Fonte: <a href="{url}" target="_blank">SSD-Sistemas Produtores</a></p>', unsafe_allow_html=True)

        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ") 
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ") 
        st.write(" ") 
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ") 

        colun_grafico1, colun_grafico2, colun_grafico3 = st.columns([1.2, 1.5, 0.15])
        with colun_grafico1:
            st.write("""
                <div class="align-left-center">
                    <div style="color: black;">
                        <p style="font-size: 11px">Agência de Água do Estado de São Paulo</h1>
                    </div>
                </div>
                """,
                    unsafe_allow_html=True)

        with colun_grafico3:
            st.markdown('<div class="align-right">', unsafe_allow_html=True)
            st.image("spaguas.png", caption="", width=300)
            st.markdown('</div>', unsafe_allow_html=True)

        with colun_grafico2:
            st.write("""
            <div style="color: black;">
                <h1  style="font-size: 16px;">Sistema Produtores da RMSP</h1>
            </div>
            """,
            unsafe_allow_html=True)

        st.write(" ") 
        st.write(" ")
        st.write(" ")
        st.write(" ")

        colun1, colun2= st.columns([1.0, 1.0])
        with colun1:
            for col in ['VolumeAtual (%)', 'Volume Ano Anterior (%)']:
                merged_data_sistemas[col] = merged_data_sistemas[col].astype(float)

                fig, ax = plt.subplots(figsize=(7, 5)) 

                # Configurações das barras
                n = len(merged_data_sistemas) 
                largura_barra = 0.30 
                espacamento = 0.05
                indice = np.arange(n) 

                # Offset calculado corretamente
                offset = np.array([-0.5, 0.5]) * (largura_barra + espacamento/2)
                cores = ['#83c4d6', '#5169af']

                # Ajuste do eixo Y
                max_valor = merged_data_sistemas[['VolumeAtual (%)', 'Volume Ano Anterior (%)']].max().max()
                ax.set_ylim(0, max_valor * 1.2)

                # Plotagem das barras
                for i, (coluna, cor) in enumerate(zip(
                    ['VolumeAtual (%)', 'Volume Ano Anterior (%)'],
                    cores
                )):
                    valores = merged_data_sistemas[coluna]
                    posicoes_x = indice + offset[i]
                    
                    barras = ax.bar(
                        posicoes_x,
                        valores,
                        largura_barra,
                        color=cor,
                        alpha=0.8,
                        label=coluna
                    )
                    
                    # Adicionando os valores dentro das barras, perto do topo
                    for x, y in zip(posicoes_x, valores):
                        ax.text(
                            x,
                            y - max_valor * 0.02,  # Um pouco abaixo do topo
                            f'{y:.0f}',           # Número inteiro com símbolo de porcentagem
                            ha='center',
                            va='top',
                            fontsize=8,
                            color='black',
                            zorder=4
                        )
                # Personalização do gráfico
                ax.set_title('Comparação entre volume atual x volume no ano anterior (%)', fontsize=10, pad=30)
                ax.set_xlabel('Mananciais', fontsize=8)
                ax.set_ylabel('Volume (%)', fontsize=8)
                ax.set_xticks(indice)
                ax.set_xticklabels(merged_data_sistemas['Sistema'], rotation=45, ha='right', fontsize=8)
                ax.grid(axis='y', linestyle=':', alpha=0.3)
                


                # Legenda fora do gráfico
                ax.legend(
                    frameon=True,
                    facecolor='#f0f0f0',
                    fontsize=7,
                    bbox_to_anchor=(0.5, 1.1),  # (posição horizontal, posição vertical)
                    loc='upper center',  # Âncora no centro superior
                    ncol=4  # Número de colunas para distribuir os itens
                )

            plt.tight_layout()
            st.pyplot(fig)

        with colun2: 
            styled_df = merged_data_sistemas.style\
            .format({
                    'VolumeAtual (%)': '{:.2f}', 
                    'Volume Ano Anterior (%)': '{:.2f}', 
                    'Diferença Vol. Anual (%)': '{:.2f}', 
                    'Chuva (mm)': '{:.0f}',
                    'Acumulado no Mês (mm)': '{:.0f}', 
                    'Média Histórica (mm)': '{:.0f}'
                })\
            .hide(axis="index")\
            .set_caption("Volume dos Sistemas Produtores (Sabesp)")\
            .set_table_styles([
                {"selector": "caption", "props": [
                    ("color", "black"),
                    ("font-size", "12px"),
                    ("font-weight", "bold"),
                    ("text-align", "center"),
                    ("padding", "5px"),
                    ("caption-side", "top") 
                ]},
                {"selector": "th", "props": [ #cabeçalho
                    ("font-size", "12px"),
                    ("height", "12px"), 
                    ("background-color", "#f0f0f0"),
                    ("color", "#333333"),
                    ("padding", "5px"),
                    ("text-align", "center")
                    ]},
                {"selector": "td", "props": [
                    ("font-size", "12px"),
                    ("height", "7px"),
                    ("color", "#333333"),
                    ("padding", "4px 5px"),
                    ("text-align", "center"),
                    ("width", "80px")
                    # ("border-bottom", "1px solid #e0e0e0")
                    ]},
                {"selector": "tr:hover", "props": [(
                    "background-color", "#ffff99"),
                    ("cursor", "pointer")
                    ]},

                {"selector": "th.col0", "props": [("width", "80px"), ("height", "50px")]},
                {"selector": "td.col0", "props": [("width", "80px"), ("height", "50px")]},
                {"selector": "th.col1", "props": [("width", "50px")]},
                {"selector": "td.col1", "props": [("width", "50px")]},
                {"selector": "th.col2", "props": [("width", "100px")]},
                {"selector": "td.col2", "props": [("width", "100px")]},
                {"selector": "th.col3", "props": [("width", "100px")]},
                {"selector": "td.col3", "props": [("width", "100px")]},
                {"selector": "th.col4", "props": [("width", "50px")]},
                {"selector": "td.col4", "props": [("width", "50px")]},
                {"selector": "th.col5", "props": [("width", "100px")]},
                {"selector": "td.col5", "props": [("width", "100px")]},
                {"selector": "th.col6", "props": [("width", "100px")]},
                {"selector": "td.col6", "props": [("width", "100px")]}
            ])\
            .set_properties(**{"background-color": "#f9f9f9", "color": "#333333"})
            st.markdown(styled_df.to_html(), unsafe_allow_html=True)


        min_dif_filter = merged_data_sistemas[merged_data_sistemas["Diferença Vol. Anual (%)"] == merged_data_sistemas["Diferença Vol. Anual (%)"].min()].iloc[0]
        max_dif_filter = merged_data_sistemas[merged_data_sistemas["Diferença Vol. Anual (%)"] == merged_data_sistemas["Diferença Vol. Anual (%)"].max()].iloc[0]

        # Acesse o valor escalar com .iloc[0]
        legenda = ""

        # Verifica se existe valor negativo
        if min_dif_filter["Diferença Vol. Anual (%)"] < 0:
            legenda += (
                f"O sistema reprodutor da Rede Metropolitana de São Paulo (RMSP) {min_dif_filter['Sistema']} "
                f"está a {min_dif_filter['Diferença Vol. Anual (%)']:.2f}% do volume últil em comparação com o mesmo mês no ano anterior, a maior diferença negativa em comparação com os demais sismtas."
                f"Atualmente o seu volume últil está em {min_dif_filter['VolumeAtual (%)']:.2f}% e no ano anterior estava com {min_dif_filter['Volume Ano Anterior (%)']:.2f}%."
            )

        # Verifica se existe valor positivo
        if max_dif_filter["Diferença Vol. Anual (%)"] > 0:
            frase_inicial = "Já o sistema" if legenda else "O sistema reprodutor da Rede Metropolitana de São Paulo (RMSP)"
            legenda += (
                f" {frase_inicial} {max_dif_filter['Sistema']} "
                f"apresentou a maior diferença positiva de {max_dif_filter['Diferença Vol. Anual (%)']:.2f}% em comparação com o mesmo mês no ano anterior, "
                f"hoje apresenta o volume atual de {max_dif_filter['VolumeAtual (%)']:.2f}% e no ano anterior estava com {max_dif_filter['Volume Ano Anterior (%)']:.2f}%."
            )


        print(legenda)

        if 'user_input_slide6' not in st.session_state:
            st.session_state.user_input_slide6 = legenda
        
        user_input = st.text_area("Análise dos Sistemas Produtores", value=st.session_state.user_input_slide6, height=100, key="user_input_slide6")
        
        st.write(" ")
        st.write(" ") 
        st.write(" ") 
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ") 
        st.write(" ") 
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ") 
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ") 
        

async def slide7():
    with slide7_container:
        col1, col2, col3 = st.columns([0.6, 2.2, 0.15])

        with col1:
            st.write("""
                <div class="align-left-center">
                    <div style="color: black;">
                        <p style="font-size: 11px">Agência de Água do Estado de São Paulo</h1>
                    </div>
                </div>
                """,
                    unsafe_allow_html=True)

        with col3:
            st.markdown('<div class="align-right">', unsafe_allow_html=True)
            st.image("spaguas.png", caption="", width=300)
            st.markdown('</div>', unsafe_allow_html=True)

        with col2:
            
            st.write(f"""
            <div style="color: black;">
                <h1  style="font-size: 16px;">Acumulados das Últimas 72h e Limiares Críticos do PPDC dos Municípios do Estado de São Paulo</h1>
            </div>
            """,
            unsafe_allow_html=True) 
        

        coluna1, coluna2 = st.columns([1.5, 0.5])
        query_cities = f"""SELECT c.name as city_name,
                            max(ac_72h) AS max_ac_72h,
                            avg(ac_mensal) AS ac_mensal,
                            ppdc,
                            c.cod_ibge,
                            fonte
                        FROM public.station_rainfall_accum_month re
                            LEFT JOIN cities c ON c.id = re.city_id
                        WHERE ac_72h IS NOT null and c.name!='Município não Existente ou Incorporado por Outro'
                        GROUP BY city_name, ppdc, c.cod_ibge, fonte
                        ORDER BY max_ac_72h DESC;"""

        tabela_df= execute_query(query_cities)

        tabela_df['status'] = 'Sem dados' 
        tabela_df.loc[tabela_df['max_ac_72h'] > tabela_df['ppdc'], 'status'] = 'Atenção'
        tabela_df.loc[tabela_df['max_ac_72h'] < tabela_df['ppdc'], 'status'] = 'Normal'
        tabela_df['max_ac_72h'] = tabela_df['max_ac_72h'].astype(float)
        tabela_df['ppdc'] = tabela_df['ppdc'].astype(float)

        shapefile_path = "data/DIV_MUN_SP_2021a.shp"
        gdf = gpd.read_file(shapefile_path)

        merged_data = pd.merge(gdf, tabela_df, left_on='GEOCODIGO', right_on='cod_ibge', how='left')
        shapefile_path_limite = "data/limiteestadualsp.shp"

        gdf_limite = gpd.read_file(shapefile_path_limite)

        if gdf_limite.crs != "EPSG:4326":
            gdf_limite = gdf_limite.to_crs(epsg=4326)

        # latitude = gdf_limite.geometry.centroid.y.mean()
        # longitude = gdf_limite.geometry.centroid.x.mean()
        latitude = -24.7594
        longitude = -48.5036


        merged_data = merged_data.to_crs(epsg=4326)

        mapa = folium.Map(
            location=[latitude, longitude],  # Centralizar no meio dos pontos
            zoom_start=5.5,
            tiles=None,
            control_scale=False, 
            zoomControl=False
        )

        folium.TileLayer(
            tiles='https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
            attr=' ',
            name='OpenStreetMap',
            overlay=False,
            control=True, 
        ).add_to(mapa)

        mapa.options['attributionControl'] = False

        folium.GeoJson(
            merged_data,
            name='Shapefile',
            style_function=lambda x: {
                'fillColor': get_fill_color(x),  # Cor de preenchimento
                'color': 'black',     # Cor da borda
                'weight': 0.5,          # Espessura da borda
                'fillOpacity': 0.6    # Transparência do preenchimento
            }
        ).add_to(mapa)
        
        legenda_html = """
        <div style="position: fixed; z-index:999999; bottom: 190px; left: 50%; transform: translateX(-50%); background: white; padding: 2px; border-radius: 5px; box-shadow: 0 0 3px rgba(0,0,0,0.3); display: flex; align-items: center; justify-content: center;">
            <div style="display: flex; align-items: center; margin-right: 5px;">
                <div style="width: 50px; height: 15px; background-color: #16c995; display: flex; align-items: center; justify-content: center; color: white; font-size: 8px; border-radius: 3px;">
                    <span> Normal </span>
                </div>
            </div>
            <div style="display: flex; align-items: center; margin-right: 5px;">
                <div style="width: 50px; height: 15px; background-color: #bda501; display: flex; align-items: center; justify-content: center; color: white; font-size: 8px; border-radius: 3px;">
                    <span> Atenção </span>
                </div>   
            </div>
            <div style="display: flex; align-items: center; margin-right: 5px;">
                <div style="width: 50px; height: 15px; background-color: #737491; display: flex; align-items: center; justify-content: center; color: white; font-size: 8px; border-radius: 3px;">
                    <span> Sem dados </span>
                </div>
            </div>
        </div>
        """
        with coluna1:
            # # Adicionar a legenda ao mapa
            mapa.get_root().html.add_child(Element(legenda_html))

            mapa_html = mapa._repr_html_()
            st.components.v1.html(mapa_html, width=900, height=350)
            url = 'https://cth.daee.sp.gov.br/sibh/chuva_agora'
            st.markdown(f'<p style="text-align: center; font-size: 12px">Elaborado pela equipe do SP Águas. Fonte: <a href="{url}" target="_blank">SIBH</a> </a></p>', unsafe_allow_html=True)
            st.write(" ")
            
        with coluna2:

            legenda = "O PPDC – Plano Preventivo de Defesa Civil específico para escorregamentos nas encostas da Serra do Mar no Estado de São Paulo (Decreto Estadual nº 30,860 de 04/12/1989, redefinido pelo Decreto Estadual nº42,565 de 01/12/1997) tem por objetivo principal evitar a ocorrência de mortes, com a remoção preventiva e temporária da população que ocupa as áreas de risco, antes que os escorregamentos atinjam suas moradias."
            if 'user_input_slide7' not in st.session_state:
                st.session_state.user_input_slide7 = legenda 

            st.text_area("Plano Preventivo de Defesa Civil específico para escorregamentos", height=300, key="user_input_slide7")


        tabela_df['per_ppdc'] = (tabela_df['max_ac_72h']*100)/tabela_df['ppdc']
        tabela_df = tabela_df.sort_values(by='per_ppdc', ascending=False)

        tabela = tabela_df.head(10)
        tabela = tabela.drop(columns=['cod_ibge'])

        tabela = tabela.rename(columns={'city_name': 'Município', 'max_ac_72h': 'Chuva Máx. (mm)', 'ac_mensal': 'Média Mensal (mm)', 'ppdc':'PPDC (Limiar de Chuva)', 'per_ppdc': '(%) PPDC', 'status': 'Status', 'fonte': 'Fonte'})
        
        # with coluna2:
        styled_df = tabela.style\
            .format({
                'Chuva Máx. (mm)': '{:.0f}', 
                'Média Mensal (mm)': '{:.0f}', 
                'PPDC (Limiar de Chuva)': '{:.0f}', 
                '(%) PPDC': '{:.0f}'
            })\
            .applymap(barra_colorida, subset=['(%) PPDC'])\
            .map(colorir_status, subset=['Status']) \
            .set_table_styles([
                {"selector": "thead th", "props": [("background-color", "#f0f0f0"), ("color", "#333333"), ("font-size", "12px"), ("padding", "5px 5px"),("text-align", "center")]},
                {"selector": "tbody td", "props": [("background-color", "white"), ("color", "black"), ("font-size", "11px"), ("padding", "5px 5px"), ("text-align", "center")]},
                {"selector": "tr:nth-child(odd)", "props": [("background-color", "#f9f9f9")]},
                {"selector": "tr:nth-child(even)", "props": [("background-color", "white")]},
                {"selector": "td, th", "props": [("border", "none")]},  # Remover bordas
                {"selector": "thead", "props": [("border-bottom", "1px solid black")]},  # Bordas apenas no cabeçalho
                {"selector": "tr", "props": [("height", "0.2px")]},
                {"selector": "th.col0", "props": [("width", "300px")]},
                {"selector": "td.col0", "props": [("width", "300px")]},
                {"selector": "th.col1", "props": [("width", "150px")]},
                {"selector": "td.col1", "props": [("width", "150px")]},
                {"selector": "th.col2", "props": [("width", "150px")]},
                {"selector": "td.col2", "props": [("width", "150px")]},
                {"selector": "th.col3", "props": [("width", "180px")]},
                {"selector": "td.col3", "props": [("width", "180px")]},
                {"selector": "th.col4", "props": [("width", "120px")]},
                {"selector": "td.col4", "props": [("width", "120px")]},
                {"selector": "th.col5", "props": [("width", "150px")]},
                {"selector": "td.col5", "props": [("width", "150px")]},
                {"selector": "th.col6", "props": [("width", "150px")]},
                {"selector": "td.col6", "props": [("width", "150px")]}
            ])\
            .hide(axis="index")  # Esconder o índice
        # Exibindo a tabela com estilo aplicado em HTML
        st.markdown(styled_df.to_html(), unsafe_allow_html=True)

        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")


async def slide8():
    with slide8_container:

        col1, col2, col3 = st.columns([1.2, 1.5, 0.15])

        with col1:
            st.write("""
                <div class="align-left-center">
                    <div style="color: black;">
                        <p style="font-size: 11px">Agência de Água do Estado de São Paulo</h1>
                    </div>
                </div>
                """,
                    unsafe_allow_html=True)

        with col3:
            st.markdown('<div class="align-right">', unsafe_allow_html=True)
            st.image("spaguas.png", caption="", width=300)
            st.markdown('</div>', unsafe_allow_html=True)

        with col2:
            url = 'https://cth.daee.sp.gov.br/sibh/chuva_agora'
            st.write(f"""
            <div style="color: black;">
                <h1  style="font-size: 16px;">Previsão do Tempo</h1>
            </div>
            """,
            unsafe_allow_html=True) 
        
        coluna1, coluna2 = st.columns([1.0, 1.0])

        data_inicial = datetime.today()
        data_inicial_str = data_inicial.strftime('%Y-%m-%d')

        url = f"https://apivime.inmet.gov.br/COSMO7/SE/prec24h/{data_inicial_str}H00:00"
        response = requests.get(url, verify=False)
        if response.status_code == 200:

            data = response.json()

            image_data = next((item for item in data if item["validade"] == 24), None)

            if image_data:
                # Extrai a string base64 da imagem
                img_base64 = image_data["base64"].split("base64,")[-1]  # Remove a parte inicial 'data:image/jpg;base64,'

                # Decodifica a imagem
                img_data = base64.b64decode(img_base64)

                # Abre a imagem usando PIL
                image = Image.open(BytesIO(img_data))


        with coluna1:

            st.image(image, caption="", use_container_width=True)
            fonte = "https://vime.inmet.gov.br/"
            st.write(f"""
                    <div style="color: black;">
                        <p style="font-size: 10px; margin: 0.5; text-align: center";">Fonte: <a href="{fonte}" target="_blank">Inmet</a></p>  
                    </div>
                """,
            unsafe_allow_html=True)


        with coluna2:
            data = datetime.today()
            data_atual_str = data.strftime('%d-%m-%Y').replace('-', '/')

            st.write(f"""
                    <div style="color: black; line-height: 1;">
                        <p style="font-size: 12px; margin: 0.5; text-align: center";"><strong>Previsão do Tempo para os dias seguintes:</strong></p>
                        <p style="font-size: 10px; margin: 0.5; text-align: center"; padding: 0; text-align: justify;">Sexta-feira {data_atual_str}</p>  
                    </div>
                """,
            unsafe_allow_html=True) 

            legenda = "Clique para editar"
            if 'user_input' not in st.session_state:
                st.session_state.user_input = legenda
            
            user_input = st.text_area("Previsão personalizada", value=st.session_state.user_input, height=100, label_visibility="collapsed")
            


async def slide8_seca():
    with slide8_secas:

        col1, col2, col3 = st.columns([1.2, 1.5, 0.15])

        with col1:
            st.write("""
                <div class="align-left-center">
                    <div style="color: black;">
                        <p style="font-size: 11px">Agência de Água do Estado de São Paulo</h1>
                    </div>
                </div>
                """,
                    unsafe_allow_html=True)

        with col3:
            st.markdown('<div class="align-right">', unsafe_allow_html=True)
            st.image("spaguas.png", caption="", width=300)
            st.markdown('</div>', unsafe_allow_html=True)

        with col2:
            url = 'https://cth.daee.sp.gov.br/sibh/chuva_agora'
            st.write(f"""
            <div style="color: black;">
                <h1  style="font-size: 16px;">Pentada</h1>
            </div>
            """,
            unsafe_allow_html=True) 
        
        coluna1, coluna2 = st.columns([1.0, 1.0])

        data_inicial = datetime.today()
        data_inicial_str = data_inicial.strftime('%Y-%m-%d')

        url = f"https://apivime.inmet.gov.br/COSMO7/SE/prec24h/{data_inicial_str}H00:00"
        response = requests.get(url, verify=False)
        if response.status_code == 200:

            data = response.json()

            image_data = next((item for item in data if item["validade"] == 120), None)

            if image_data:
                # Extrai a string base64 da imagem
                img_base64 = image_data["base64"].split("base64,")[-1]  # Remove a parte inicial 'data:image/jpg;base64,'

                # Decodifica a imagem
                img_data = base64.b64decode(img_base64)

                # Abre a imagem usando PIL
                image = Image.open(BytesIO(img_data))

        with coluna1:

            st.image(image, caption="", use_container_width=True)
            fonte = "https://vime.inmet.gov.br/"
            st.write(f"""
                    <div style="color: black;">
                        <p style="font-size: 10px; margin: 0.5; text-align: center";">Fonte: <a href="{fonte}" target="_blank">Inmet</a></p>  
                    </div>
                """,
            unsafe_allow_html=True)


        with coluna2:
            data = datetime.today()
            data_atual_str = data.strftime('%d-%m-%Y').replace('-', '/')

            st.write(f"""
                    <div style="color: black; line-height: 1;">
                        <p style="font-size: 12px; margin: 0.5; text-align: center";"><strong>Previsão do Tempo para os dias seguintes:</strong></p>
                        <p style="font-size: 10px; margin: 0.5; text-align: center"; padding: 0; text-align: justify;">Sexta-feira {data_atual_str}</p>  
                    </div>
                """,
            unsafe_allow_html=True) 

            if 'user_input' not in st.session_state:
                st.session_state.user_input = "Clique para editar"
            
            user_input = st.text_area("", value=st.session_state.user_input, height=100)
            
            if user_input != st.session_state.user_input:
                st.session_state.user_input = user_input
        

async def slide5_seca(): 
    with slide5_secas:

        col1, col2, col3 = st.columns([1.2, 1.5, 0.15])

        with col1:
            st.write("""
                <div class="align-left-center">
                    <div style="color: black;">
                        <p style="font-size: 11px">Agência de Água do Estado de São Paulo</h1>
                    </div>
                </div>
                """,
                    unsafe_allow_html=True)

        with col3:
            st.markdown('<div class="align-right">', unsafe_allow_html=True)
            st.image("spaguas.png", caption="", width=300)
            st.markdown('</div>', unsafe_allow_html=True)

        with col2:
            st.write(f"""
            <div style="color: black;">
                <h1  style="font-size: 16px;">Dados Fluviometria - Seca</h1>
            </div>
            """,
            unsafe_allow_html=True)

        url = "https://cth.daee.sp.gov.br/sibh/api/v2/measurements/now_flu?references%5B%5D=l95&with_all_ref=true"

        response = requests.get(url)

        if response.status_code == 200:

            data = response.json()

            if 'measurements' in data and data['measurements']:
                
                df_seca = pd.DataFrame(data['measurements'])

                df_seca['value'] = pd.to_numeric(df_seca['value'], errors='coerce')
                df_seca['l95'] = pd.to_numeric(df_seca['l95'], errors='coerce')
                df_seca['latitude'] = pd.to_numeric(df_seca['latitude'], errors='coerce')
                df_seca['longitude'] = pd.to_numeric(df_seca['longitude'], errors='coerce')
                df_seca = df_seca.sort_values(by="value", ascending=False)     



                df_seca['current_state'] = df_seca.apply(classify_state_seca, axis=1)
                df_seca = df_seca[df_seca['current_state']!='Níveis Indefinidos']

                mapa = folium.Map(
                    location=[-22.7832, -48.4430],  # Centralizar no meio dos pontos
                    zoom_start=6.5,
                    tiles=None,
                    control_scale=False, 
                    zoomControl=False
                )

                folium.TileLayer(
                    tiles='https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
                    attr=' ',
                    name='OpenStreetMap',
                    overlay=False,
                    control=True
                ).add_to(mapa)

                mapa.options['attributionControl'] = False

                shapefile_path = "data/limiteestadualsp.shp"
                gdf = gpd.read_file(shapefile_path)

                folium.GeoJson(
                    gdf,
                    name='Shapefile',
                    style_function=lambda x: {
                        'fillColor': '#808080',  # Cor de preenchimento
                        'color': 'black',     # Cor da borda
                        'weight': 0.5,          # Espessura da borda
                        'fillOpacity': 0.2    # Transparência do preenchimento
                    }
                ).add_to(mapa)

                normal_layer = folium.FeatureGroup(name='Normal')
                atencao_layer = folium.FeatureGroup(name='Atenção - l95')

                # Adicionar marcadores para cada ponto
                for index, row in df_seca.iterrows():
                    lat = row['latitude']
                    lon = row['longitude']
                    valor = row['value']
                    state = row['current_state']

                    valor_inteiro = int(valor)
                    popup = f"Valor: {valor}"
                    
                    valor_inteiro = int(valor)

                    if valor_inteiro>0:
                        # Criar um popup com o valor
                        popup = f"Valor: {valor}"

                        if state == 'Atenção - l95':
                            folium.CircleMarker(
                                location=[lat, lon],
                                radius=4,  # Tamanho do marcador
                                color="black",  # Borda branca
                                weight=0.3,  # Espessura da borda
                                fill=True,
                                fill_color="#bda501",
                                fill_opacity=1.0,
                                popup=popup
                            ).add_to(atencao_layer)

                        else: 
                            folium.CircleMarker(
                                location=[lat, lon],
                                radius=4,  # Tamanho do marcador
                                color="black",  # Borda branca
                                weight=0.3,  # Espessura da borda
                                fill=True,
                                fill_color='#16c995',
                                fill_opacity=1.0,
                                popup=popup
                            ).add_to(normal_layer)

                normal_layer.add_to(mapa)
                atencao_layer.add_to(mapa)

                folium.LayerControl().add_to(mapa)
                
                legenda_html = """
                <div style="position: fixed; z-index:999999; bottom: 22px; left: 50%; transform: translateX(-50%); background: white; padding: 2px; border-radius: 5px; display: flex; align-items: center; justify-content: center;">
                    <div style="display: flex; align-items: center; margin-right: 5px;">
                        <div style="width: 60px; height: 15px; background-color: #f74f78; display: flex; align-items: center; justify-content: center; color: white; font-size: 8px; border-radius: 3px;">
                            <span> Emergência -l7</span>
                        </div>   
                    </div>
                    <div style="display: flex; align-items: center; margin-right: 5px;">
                        <div style="width: 60px; height: 15px; background-color: #bda501; display: flex; align-items: center; justify-content: center; color: white; font-size: 8px; border-radius: 3px;">
                            <span> Atenção - l95</span>
                        </div>   
                    </div>
                    <div style="display: flex; align-items: center; margin-right: 5px;">
                        <div style="width: 60px; height: 15px; background-color: #16c995; display: flex; align-items: center; justify-content: center; color: white; font-size: 8px; border-radius: 3px;">
                            <span> Normal</span>
                        </div>
                    </div>
                </div>
                """
                mapa.get_root().html.add_child(Element(legenda_html))

                mapa_html = mapa._repr_html_()
                # mapa.save("mapa_com_legenda.html")

                c1, c2, c3 = st.columns([0.1, 1.2, 0.1])
                with c2:
                    # folium_static(mapa, width=600, height=400)
                    st.components.v1.html(mapa_html, width=1000, height=580)
                
                colun1, colun2, colun3 = st.columns([0.2, 1.2, 0.2])
                with colun2:    
                    url_sib = "https://cth.daee.sp.gov.br/sibh/chuva_agora"
                    st.write(f"""
                            <div style="color: black; line-height: 1;">
                                <p style="text-align: center; font-size: 12px; margin: 0; padding: 0;">Fonte: Chuva agora - <a href="{url_sib}" target="_blank"> SIBH</a></p>
                            </div>
                            """,
                        unsafe_allow_html=True)
                    
                    if 'user_input_slide5_seca' not in st.session_state:
                        st.session_state.user_input_slide5_seca = "Clique aqui para editar" # sem f-string desnecessária

                        st.text_area("Análise das redes Telemétrica", height=100, key="user_input_slide5_seca")
            
            st.write(" ")
            st.write(" ")
            st.write(" ")
            st.write(" ")
            st.write(" ")
            st.write(" ")
                   

async def capa_boletim():
    with capa_boletim_container:

            
        col_logo_1, col_logo_2, col_logo_3 = st.columns([0.4, 1.50, 0.30])
        with col_logo_1:
            st.image("spaguas.png", caption="", width=80)

        with col_logo_2:
            st.write(f"""
            <div style="text-align: center; color: black;">
                <p style="text-align: center; font-size: 16px;">Escolha o tipo de relatório </p>
            </div>
            """,
                unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)


            button_style = """
                <style>
                    .stButton>button {
                        background-color: white;
                        border: 2px solid blue;
                        color: blue;
                        font-size: 16px;
                        font-weight: bold;
                        border-radius: 5px;
                        padding: 10px 20px;
                        cursor: pointer;
                    }
                    .stButton>button:hover {
                        background-color: lightblue;
                    }
                </style>
            """

            # Adicionando o CSS à página
            st.markdown(button_style, unsafe_allow_html=True)

            col1, col2 = st.columns(2)
            if col1.button("Relatório de chuvas", use_container_width=True):
                st.session_state.boletim = "chuvas"
                st.session_state.selecionado = True
                
            if col2.button("Relatório de secas", use_container_width=True):
                st.session_state.boletim = "secas"
                st.session_state.selecionado = True

async def slide6_seca(): 
    with slide6_secas:
        col1, col2, col3 = st.columns([1.2, 1.5, 0.15])

        with col1:
            st.write("""
                <div class="align-left-center">
                    <div style="color: black;">
                        <p style="font-size: 11px">Agência de Água do Estado de São Paulo</h1>
                    </div>
                </div>
                """,
                    unsafe_allow_html=True)

        with col3:
            st.markdown('<div class="align-right">', unsafe_allow_html=True)
            st.image("spaguas.png", caption="", width=300)
            st.markdown('</div>', unsafe_allow_html=True)

        with col2:
            st.write(f"""
            <div style="color: black;">
                <h1  style="font-size: 16px;">Sistema Alto Tietê - Seca</h1>
            </div>
            """,
            unsafe_allow_html=True)

        st.write(" ")


        url = 'https://cth.daee.sp.gov.br/ssdsp/Sistema/AltoTiete'
        response = requests.get(url)

        # Verifica se a requisição foi bem sucedida
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')

            # Encontra a tabela pela classe
            table = soup.find('table', class_='table-systems')

            # Extrai os dados do tbody
            rows = table.find('tbody').find_all('tr')

            # Monta os dados
            data = []
            for row in rows:
                cols = row.find_all('td')
                data.append([col.text.strip() for col in cols])

            # Cria o DataFrame
            tabela = pd.DataFrame(data, columns=[
                "Represa",
                "Volume Total (hm³)",
                "Volume Útil (hm³)",
                "Volume Útil (%)",
                "Vazão Afluente (m³/s)",
                "Vazão Defluente (m³/s)",
                "Chuva (mm)"
            ])

            print(tabela)

            styled_df = tabela.style\
            .set_table_attributes('style="width:100%; table-layout:fixed"')\
            .set_table_styles([
                {"selector": "thead th", "props": [("background-color", "#f0f0f0"), ("color", "#333333"), ("font-size", "12px"), ("padding", "5px 5px"),("text-align", "center")]},
                {"selector": "tbody td", "props": [("background-color", "white"), ("color", "black"), ("font-size", "12px"), ("padding", "5px 5px"), ("text-align", "center"), ("line-height", "3.0")]},
                {"selector": "tbody tr:nth-child(odd)", "props": [("background-color", "#f9f9f9")]},

                # Largura específica para colunas (baseado na ordem do DataFrame)
                {"selector": "td:nth-child(1), th:nth-child(1)", "props": [("width", "120px")]},  # Represa
                {"selector": "td:nth-child(2), th:nth-child(2)", "props": [("width", "80px")]},   # Volume Total
                {"selector": "td:nth-child(3), th:nth-child(3)", "props": [("width", "80px")]},   # Volume Útil
                {"selector": "td:nth-child(4), th:nth-child(4)", "props": [("width", "80px")]},   # Volume Útil %
                {"selector": "td:nth-child(5), th:nth-child(5)", "props": [("width", "80px")]},   # Vazão Afluente
                {"selector": "td:nth-child(6), th:nth-child(6)", "props": [("width", "80px")]},   # Vazão Defluente
                {"selector": "td:nth-child(7), th:nth-child(7)", "props": [("width", "80px")]}    # Chuva
            ])\
                .hide(axis="index") 
            
        colun1, colun2 = st.columns([1.0, 1.0])

        with colun1:
            st.write("""
                <div style="text-align: center; color: #333333;">
                    <h1  style="font-size: 10px; margin: 0; padding: 0">Dados do sistema Alto Tietê</h1>
                </div>
                """,
            unsafe_allow_html=True)
            st.write(" ")
            st.markdown(styled_df.to_html(), unsafe_allow_html=True)

            st.write(f"""
                <div style="color: black; line-height: 1;">
                    <p style="text-align: center; font-size: 10px; margin: 0; padding: 0;">Fonte: SSSD Alto Tietê - <a href="{url}" target="_blank"> CTH - DAEE </a></p>
                </div>
                """,
            unsafe_allow_html=True)
        
        
        with colun2:
            st.write("""
                <div style="text-align: center; color: #333333;">
                    <h1  style="font-size: 10px; margin: 0; padding: 0">Diagrama unifiliar do Alto Tietê</h1>
                </div>
                """,
            unsafe_allow_html=True)
            imagem = capturar_tela(url)
            imagem_recortada = imagem.crop((130, 1860, 1300, 2500)) #esquerda, cima, direita, baixo


            st.image(imagem_recortada, caption="", use_container_width=True)

            st.write(f"""
                <div style="color: black; line-height: 1;">
                    <p style="text-align: center; font-size: 10px; margin: 0; padding: 0;">Fonte: SSSD Alto Tietê - <a href="{url}" target="_blank"> CTH - DAEE </a></p>
                </div>
                """,
            unsafe_allow_html=True)

        c1, c2, c3 = st.columns([0.2, 1.2, 0.2])

        with c2:
            st.write(" ")
            st.write(" ")
            st.write(" ")
            if 'user_input_slide6_seca' not in st.session_state:
                st.session_state.user_input_slide6_seca = "Clique para editar"
            
            user_input = st.text_area("Análise do Sistema Produtor - Alto Tietê", value=st.session_state.user_input_slide6_seca, height=100, key="user_input_slide6_seca")
        
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")


        
    

async def main():
    
    if 'boletim' not in st.session_state:
        # Se ainda não tiver boletim escolhido, exibe a tela de seleção
        await capa_boletim()
    else:
        # Limpar a tela de seleção e exibir os slides
        st.empty()

        # Executa todas as tasks simultaneamente
        if st.session_state.boletim == 'chuvas':
            await asyncio.gather(
                capa(),
                slide1(),
                slide2(),
                slide3(),
                # slide4(), não será mais usado
                slide5(),
                slide6(),
                slide7(),
                slide8()
            )
        elif st.session_state.boletim == 'secas':
            await asyncio.gather(
                capa(),    
                slide1_seca(),
                slide1(),
                slide2(),
                slide5_seca(),
                slide6(),
                slide6_seca(),
                slide8_seca()
            )

    
if __name__ == "__main__":
    asyncio.run(main())




