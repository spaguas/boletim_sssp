import os
import io
import folium
import requests
import tempfile
import shutil
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import geopandas as gpd
import plotly.express as px
import time as tm
import psycopg2 as pg
import matplotlib.cm as cm
import urllib.parse
import base64
import asyncio
import json
import plotly.graph_objects as go
import branca.colormap as cmb
import platform
import matplotlib.dates as mdates
from osgeo import gdal, ogr, osr
from rasterstats import zonal_stats
from datetime import datetime, timedelta, time, date
from PIL import Image, ImageOps
from branca.element import Element
from streamlit.components.v1 import html
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from PIL import Image
from io import BytesIO
from matplotlib import pyplot as plt
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from matplotlib.colors import Normalize, rgb2hex
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from folium import Popup
from fpdf import FPDF
from html2image import Html2Image
from concurrent.futures import ThreadPoolExecutor
from dateutil.relativedelta import relativedelta
from matplotlib.patches import FancyArrowPatch
from shapely.geometry import Point
from urllib.parse import quote


load_dotenv()

class PDF(FPDF):
    def __init__(self, orientation='L'):  # 'L' para Landscape (Paisagem)
        super().__init__(orientation=orientation, unit='mm', format='A4')
        self.set_margins(0, 0, 0)
        self.set_auto_page_break(auto=False)
        self.logo_path = "spaguas.png"
        
    def header(self):
        if self.show_header:
            self.set_font('Arial', '', 9)
            col1_w = 45
            col3_w = 30
            y = 10
            self.set_xy(10, y)
            self.cell(col1_w, 10, "Agência de Água do Estado de São Paulo", 0, 0, 'L')
            if os.path.exists(self.logo_path):
                self.image(self.logo_path, x=self.w - col3_w - 10, y=y-3, w=20)
        else:
            # Não imprime nada (nenhum cabeçalho)
            pass
    
    def footer(self):
        # Adicionar rodapé se necessário
        pass


st.set_page_config(layout="wide")

capa_boletim_container = st.container()
escolha_reservatorio_container = st.container()
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


users = os.environ.get('USERS').split(";")
users_dict = {u.split(":")[0]: u.split(":")[1] for u in users}

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
        df = pd.DataFrame(rows, columns=colunas)

        return df

    except Exception as e:
        print(f"Erro ao executar a query: {e}")
        return None

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

def get_text_height(pdf, text, w, line_height):
    if isinstance(text, tuple):
        text = text[0]
    # Quebra o texto em linhas considerando a largura
    lines = pdf.multi_cell(w, line_height, txt=text, border=0, split_only=True)
    return len(lines) * line_height

def localizar_chrome():
    sistema = platform.system()

    # Caminhos padrão por sistema
    caminhos_possiveis = []
    if sistema == "Windows":
        caminhos_possiveis = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
        ]
    elif sistema == "Linux":
        caminhos_possiveis = [
            "/usr/bin/google-chrome",
            "/usr/bin/chromium-browser"
        ]


    # Procura o primeiro caminho existente
    for caminho in caminhos_possiveis:
        if os.path.exists(caminho):
            return caminho

    return None

def transform_html_image(nome_arquivo):

    chrome_path = localizar_chrome()
    png_path = f'imagens/{nome_arquivo}.png'
    
    # Garante que o diretório existe
    os.makedirs("imagens", exist_ok=True)
    
    if os.path.exists(png_path):
        os.remove(png_path)

    # Usa o mesmo Chrome do Selenium (caminho explícito)
    hti = Html2Image(
        output_path='imagens',
        custom_flags=[
            "--headless=new",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--force-device-scale-factor=5"
        ]
    )

    hti.browser_path = chrome_path

    try:
        hti.screenshot(
            html_file=f'{nome_arquivo}.html',
            save_as=f'{nome_arquivo}.png',
            size=(800, 600)
        )
        print(f"[SUCESSO] Screenshot salvo em: {png_path}")
    except Exception as e:
        print(f"[ERRO] Falha ao gerar imagem: {str(e)}")
        raise

def wait_for_file(filepath, timeout=30):
    start_time = tm.time()
    while not os.path.exists(filepath):
        if tm.time() - start_time > timeout:
            raise FileNotFoundError(f"Arquivo {filepath} não gerado em {timeout}s")
        tm.sleep(2)
    return True

def remove_transparency(image_path):
    im = Image.open(image_path)
    if im.mode in ('RGBA', 'LA'):
        bg = Image.new("RGB", im.size, (255, 255, 255))  # fundo branco
        bg.paste(im, mask=im.split()[3])  # usa o alpha como máscara
        bg.save(image_path)
    else:
        im.convert("RGB").save(image_path)    
                
def create_pdf(user_input1, image, user_input3, user_input5, all_extravasamento, user_input6, user_input7, user_input8, url):
    # Cria PDF em modo paisagem
    pdf = PDF(orientation='L')

    #Capa
    pdf.show_header = False
    pdf.add_page()

    img = Image.open("Logo Colorido.png").convert("RGBA")
    alpha = 60  # 0 (totalmente transparente) a 255 (opaco)
    img.putalpha(alpha)
    bg = Image.new("RGB", img.size, (255, 255, 255))
    bg.paste(img, mask=img.split()[3])
    bg.save("logo_temp.jpg", "JPEG")
    pdf.image("logo_temp.jpg", x=25, y=-2, w=350)

    pdf.set_xy(10, 85)
    pdf.set_font("Arial", "B", 30)
    pdf.cell(0, 10, "Boletim Diário", ln=True)

    pdf.set_xy(10, 95)
    pdf.set_font("Arial", "B", 15)
    pdf.cell(0, 10, "Sala de Situação São Paulo - SSSP", ln=True)

    data_atual = datetime.today()
    data_anterior = datetime.today() - timedelta(days=1)
    data_atual_str = data_atual.strftime('%d-%m-%Y').replace('-', '/')
    data_anterior_str = data_anterior.strftime('%d-%m-%Y').replace('-', '/')

    pdf.set_xy(10, 102)
    pdf.set_font("Arial", "B", 15)
    pdf.cell(0, 10, f"{data_anterior_str} 07:00 até {data_atual_str} 07:00", ln=True)
    
    imagem_logos = "regua.png"
    pdf.image(imagem_logos, x=165, y=193, w=130)

    #________________________________________________________________Slide 1
    try:
        pdf.show_header = True 
        pdf.add_page()

        col1_w = 80 
        col2_w = 120  
        col3_w = 165  
    
        pdf.set_xy(col2_w, 15)
        pdf.set_font("Arial", size=14,style='B')
        pdf.cell(col2_w, txt="Dados Pluviometria", ln=1, align='L')
        pdf.set_font("Arial", size=12)

        pdf.set_xy(38, 26)
        pdf.set_font("Arial","B", size=12)
        pdf.cell(0, 10, txt="Acumulado de chuva das ultimas 24h", ln=1)

        mapa_html_flu = 'mapa_html_flu'
        transform_html_image(mapa_html_flu)
        tm.sleep(10)

        imgagem_flu = Image.open("imagens/mapa_html_flu.png").convert("RGBA")
        # background.paste(imgagem_flu, mask=imgagem_flu.getchannel("A"))
        background = Image.new("RGB", imgagem_flu.size, (255, 255, 255))  # fundo branco
        background.paste(imgagem_flu, mask=imgagem_flu.split()[3])  # usa canal alpha como máscara
        background.save("imagens/mapa_html_flu.jpg", "JPEG", quality=95)

        pdf.image("imagens/mapa_html_flu.jpg", x=10, y=36, w=136)
        pdf.set_xy(62, 124)  # x=20 (imagem), y=120 (abaixo dela)
        pdf.set_font("Arial", size=8, style='I')
        pdf.cell(0, 10, txt="Fonte: Chuva agora - SIBH", ln=1, link="https://cth.daee.sp.gov.br/sibh/chuva_agora")


        pdf.set_xy(165, 26)
        pdf.set_font("Arial","B", size=12)
        pdf.cell(0, 10, txt="Interpolação dos pluviômetros a partir do método IDW", ln=1)

        mapa_html_inter = 'mapa_html_inter'
        transform_html_image(mapa_html_inter)
        tm.sleep(10)
        imgagem_inter = Image.open("imagens/mapa_html_inter.png").convert("RGBA")
        background = Image.new("RGB", imgagem_inter.size, (255, 255, 255))  # fundo branco
        background.paste(imgagem_inter, mask=imgagem_inter.split()[3])  # usa canal alpha como máscara
        background.save("imagens/mapa_html_inter.jpg", "JPEG", quality=95)
        pdf.image("imagens/mapa_html_inter.jpg", x=150, y=36, w=136)
        pdf.set_xy(152, 125)  # x=150 (imagem), y=120 (abaixo dela)
        pdf.set_font("Arial", size=8, style='I')
        pdf.multi_cell(135, 5, txt="Elaborado pela equipe técnica da Sala de Situação São Paulo (SSSP). Parâmetros: Potência=0.02, Suavização=0.02 e Raio=0.5.", align='C')
        
        x = 10
        y = 142
        w = 278
        padding = 3
        line_height = 7

        pdf.set_xy(x, 132)
        pdf.set_font("Arial","B", size=12)
        pdf.cell(0, 10, txt="Relatos 24h", ln=1)

        cell_height = get_text_height(pdf, user_input1, w - 2 * padding, line_height)
        total_height = cell_height + 2 * padding

        pdf.set_draw_color(200, 200, 200)  # cinza claro
        pdf.rect(x, y, w, total_height)

        pdf.set_xy(x + padding, y + padding)
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(w - 2 * padding, line_height, txt=user_input1, border=0)
    
    except Exception as e:
        pdf.set_xy(col2_w, 12)
        pdf.set_font("Arial", size=14, style='B')
        pdf.multi_cell(
            150,  # largura da célula
            7,  # altura da linha
            txt=f"Erro ao gerar slide 1: {e}",
            align='C'
        )
        print("Erro ao gerar slide 1:", e)


    #________________________________________________________________Slide 2
    try: 
        pdf.show_header = True 
        pdf.add_page()

        col1_w = 80 
        col2_w = 120  
        col3_w = 165  

        pdf.set_xy(col2_w, 15)
        pdf.set_font("Arial", size=14,style='B')
        pdf.cell(col2_w, txt="Dados Pluviometria", ln=1, align='L')
        pdf.set_font("Arial", size=12)

        pdf.set_xy(10, 25)
        pdf.set_font("Arial","B", size=12)
        pdf.multi_cell(135, 7, txt="Municípios com os maiores acumulados de chuvas observadas nas últimas 24h (mm) (Rede Telemétrica)", align='C')
        imgagem_tabela = Image.open("imagens/tabela_chuva.png").convert("RGBA")
        background = Image.new("RGB", imgagem_tabela.size, (255, 255, 255))
        background.paste(imgagem_tabela, mask=imgagem_tabela.split()[3])  # usa canal alpha como máscara
        background.save("imagens/tabela_chuva.jpg", "JPEG", quality=95)
        pdf.image("imagens/tabela_chuva.jpg", x=6, y=38, w=153)
        
        pdf.set_xy(10, 113)
        pdf.set_font("Arial", size=10)
        texto = (
            "1- Máximo Registrado - Volume máximo (mm) registrado por um posto pluviométrico do município.\n"
            "2- Média Registrada - Soma do Volume (mm) de todos os postos do município / n° de postos.\n"
            "3- Acumulado média mês - Soma da média (mm) registrada do primeiro dia do mês até o momento.\n"
            "4- Histórico mensal - Volume médio mensal calculado a partir da série histórica disponível."
        )
        pdf.multi_cell(135, 5, txt=texto)

        pdf.set_xy(155, 26)
        pdf.set_font("Arial","B", size=12)
        pdf.multi_cell(135, 6, txt='Comparação de Precipitação por Município', align='C')
        pdf.image("imagens/grafico_chuva.png", x=155, y=32, w=121)

        pdf.set_xy(155, 115)
        pdf.set_font("Arial","B", size=12)
        pdf.multi_cell(135, 6, txt='Chuva média acumulada por UGRHI', align='C')
        pdf.image("imagens/grafico_chuva2.png", x=155, y=120, w=120)

    except:
        pdf.set_xy(col2_w, 12)
        pdf.set_font("Arial", size=14, style='B')
        pdf.multi_cell(
            150,  # largura da célula
            7,  # altura da linha
            txt=f"Erro ao gerar slide 2: {e}",
            align='C'
        )
        print("Erro ao gerar slide 2:", e)    

    #________________________________________________________________Slide 3
    try:
        pdf.show_header = True 
        pdf.add_page()

        col1_w = 80 
        col2_w = 120  
        col3_w = 165  
    
        pdf.set_xy(col2_w, 15)
        pdf.set_font("Arial", size=14,style='B')
        pdf.cell(col2_w, txt="Acumulados dos Radares", ln=1, align='L')
        pdf.set_font("Arial", size=12)

        data_inicial = datetime.today()
        data_str = data_inicial.strftime('%Y-%m-%d')
        pdf.set_xy(13, 26)
        pdf.set_font("Arial","B", size=12)
        pdf.multi_cell(135, 6, txt='Acumulado das 24h (mm) - Radar Ipmet', align='C')

        image_path = f'results/imagem_ipmet_{data_str}.png'
        img_ipmet = Image.open(image_path).convert("RGB")
        img_ipmet.save("imagens/imagem_ipmet_temp.jpg", "JPEG", quality=95)
        pdf.image("imagens/imagem_ipmet_temp.jpg", x=10, y=32, w=148)

        legenda_ipmet = Image.open("escala_acum.png").convert("RGB")
        legenda_ipmet.save("imagens/escala_ipmet_temp.jpg", "JPEG", quality=95)
        pdf.image("imagens/escala_ipmet_temp.jpg", x=50, y=100, w=60)

        pdf.set_xy(42, 116)  # x=20 (imagem), y=120 (abaixo dela)
        pdf.set_font("Arial", size=10, style='I')
        pdf.cell(0, 6, txt="Produzido pelo Ipmet. Disponível em: IPMET", ln=1, link="https://www.ipmetradar.com.br/2mobileGis.php")

        pdf.set_xy(163, 26)
        pdf.set_font("Arial","B", size=12)
        pdf.multi_cell(132, 6, txt='Acumulado das 24h (mm) - Radar SP Águas', align='C')

        image_path_saisp = f'results/imagem_saisp_{data_str}.png'
        img_saisp = Image.open(image_path_saisp).convert("RGB")
        img_saisp.save("imagens/imagem_saisp_temp.jpg", "JPEG", quality=95)
        pdf.image("imagens/imagem_saisp_temp.jpg", x=165, y=32, w=120)

        legenda_saisp = Image.open("imagens/Imagem1.jpg").convert("RGB")
        legenda_saisp.save("imagens/Imagem1_temp.jpg", "JPEG", quality=95)
        pdf.image("imagens/Imagem1_temp.jpg", x=165, y=155, w=120)

        pdf.set_xy(155, 164)  # x=20 (imagem), y=120 (abaixo dela)
        pdf.set_font("Arial", size=10, style='I')
        pdf.multi_cell(140, 6, txt='Produzido pelo Radar 600S-Selex, Banda S, 850 KW, Doppler, Dupla Polarização.', align='C')
        pdf.set_xy(205, 168)  # x=20 (imagem), y=120 (abaixo dela)
        pdf.set_font("Arial", size=10, style='I')
        pdf.cell(0, 6, txt="Disponível em: SAISP", ln=1, link="https://www.saisp.br/estaticos/sitenovo/home.html")
        
        x = 10
        y = 140
        w = 148
        padding = 3
        line_height = 7

        pdf.set_xy(x, 132)
        pdf.set_font("Arial","B", size=12)
        pdf.cell(0, 10, txt="Análise", ln=1)

        cell_height = get_text_height(pdf, user_input3, w - 2 * padding, line_height)
        total_height = cell_height + 2 * padding

        pdf.set_draw_color(200, 200, 200)  # cinza claro
        pdf.rect(x, y, w, total_height)

        pdf.set_xy(x + padding, y + padding)
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(w - 2 * padding, line_height, txt=user_input3, border=0)

    except Exception as e:
        pdf.add_page()
        pdf.set_xy(col2_w, 12)
        pdf.set_font("Arial", size=14, style='B')
        pdf.multi_cell(
            150,  # largura da célula
            7,  # altura da linha
            txt=f"Erro ao gerar slide 3: {e}",
            align='C'
        )
        print("Erro ao gerar slide 3:", e)


    #________________________________________________________________________Slide 5
    try: 
        pdf.show_header = True 
        pdf.add_page()

        col1_w = 80 
        col2_w = 120  
        col3_w = 165  
    
        pdf.set_xy(col2_w, 15)
        pdf.set_font("Arial", size=14,style='B')
        pdf.cell(col2_w, txt="Dados Fluviometria", ln=1, align='L')
        pdf.set_font("Arial", size=12)

        mapa_html_5 = "mapa_slide5"
        transform_html_image(mapa_html_5)
        tm.sleep(10)
        imgagem_html_5 = Image.open("imagens/mapa_slide5.png").convert("RGBA")
        # background.paste(imgagem_flu, mask=imgagem_flu.getchannel("A"))
        background = Image.new("RGB", imgagem_html_5.size, (255, 255, 255))  # fundo branco
        background.paste(imgagem_html_5, mask=imgagem_html_5.split()[3])  # usa canal alpha como máscara
        background.save("imagens/mapa_slide5.jpg", "JPEG", quality=95)
        pdf.image("imagens/mapa_slide5.jpg", x=40, y=25, w=210)
        pdf.set_xy(115, 158)  # x=20 (imagem), y=120 (abaixo dela)
        pdf.set_font("Arial", size=8, style='I')
        pdf.cell(0, 10, txt="Fonte: Chuva agora - SIBH", ln=1, link="https://cth.daee.sp.gov.br/sibh/chuva_agora")

        x = 10
        y = 170
        w = 270
        padding = 3
        line_height = 7

        pdf.set_xy(x, 160)
        pdf.set_font("Arial","B", size=12)
        pdf.cell(0, 10, txt="Análise das redes Telemétrica", ln=1)

        cell_height = get_text_height(pdf, user_input5, w - 2 * padding, line_height)
        total_height = cell_height + 2 * padding

        pdf.set_draw_color(200, 200, 200)  # cinza claro
        pdf.rect(x, y, w, total_height)

        pdf.set_xy(x + padding, y + padding)
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(w - 2 * padding, line_height, txt=user_input5, border=0)


        if all_extravasamento != None: 

            for item in all_extravasamento:
                    
                cards_img = item['cards_image']
                grafico_img = item['grafico_path']
                tabela_img = item['tabela_resumo']
                pdf.add_page()
                
                pdf.set_xy(120, 15)
                pdf.set_font("Arial", size=14,style='B')
                pdf.cell(120, txt=f"Gráfico do Extravasamento", ln=1, align='L')
                pdf.set_font("Arial", size=12)

                
                im = Image.open(f"imagens/{cards_img}")
                width, height = im.size

                # Define um fator de zoom (por exemplo, 1.5x)
                remove_transparency(f"imagens/{cards_img}")
                remove_transparency(f"imagens/{grafico_img}")
                remove_transparency(f"imagens/{tabela_img}")
                pdf.image(f"imagens/{cards_img}", x=10, y=22, w=275)
                pdf.image(f"imagens/{grafico_img}", x=6, y=52, w=285)
                pdf.image(f"imagens/{tabela_img}", x=10, y=175, w=280)
    except Exception as e:
        pdf.add_page()
        pdf.set_xy(col2_w, 12)
        pdf.set_font("Arial", size=14, style='B')
        pdf.multi_cell(
            150,  # largura da célula
            7,  # altura da linha
            txt=f"Erro ao gerar slide 5: {e}",
            align='C'
        )
        print("Erro ao gerar slide 5:", e)
    #________________________________________________________________________Slide 6
    try:
        pdf.show_header = True 
        pdf.add_page()

        col1_w = 80 
        col2_w = 120  
        col3_w = 165  
    
        pdf.set_xy(col2_w, 15)
        pdf.set_font("Arial", size=14,style='B')
        pdf.cell(col2_w, txt="Sistema Produtores da RMSP", ln=1, align='L')
        pdf.set_font("Arial", size=12)

        pdf.image("results/imagem_rmsp.png", x=15, y=25, w=265)

        pdf.set_xy(120, 189)  # x=20 (imagem), y=120 (abaixo dela)
        pdf.set_font("Arial", size=8, style='I')
        pdf.cell(0, 10, txt="Fonte: SSD-Sistemas Produtores", ln=1, link="https://cth.daee.sp.gov.br/ssdsp/")


        pdf.show_header = True 
        pdf.add_page()

        col1_w = 80 
        col2_w = 120  
        col3_w = 165  
    
        pdf.set_xy(col2_w, 15)
        pdf.set_font("Arial", size=14,style='B')
        pdf.cell(col2_w, txt="Sistema Produtores da RMSP", ln=1, align='L')
        pdf.set_font("Arial", size=12)

        pdf.set_xy(10, 26)
        pdf.set_font("Arial","B", size=12)
        pdf.multi_cell(135, 7, txt="Comparação entre volume atual x volume no ano anterior (%)", align='C')
        remove_transparency(f"imagens/grafico_rmsp.png")
        pdf.image(f"imagens/grafico_rmsp.png", x=8, y=32, w=134)

        pdf.set_xy(150, 26)
        pdf.set_font("Arial","B", size=12)
        pdf.multi_cell(135, 7, txt="Volume dos Sistemas Produtores (Sabesp)", align='C')
        remove_transparency(f"imagens/tabela_rmsp.png")
        pdf.image(f"imagens/tabela_rmsp.png", x=147, y=32, w=160)


        x = 10
        y = 150
        w = 270
        padding = 3
        line_height = 7

        pdf.set_xy(x, 140)
        pdf.set_font("Arial","B", size=12)
        pdf.cell(0, 10, txt="Análise dos Sistemas Produtores", ln=1)

        cell_height = get_text_height(pdf, user_input6, w - 2 * padding, line_height)
        total_height = cell_height + 2 * padding

        pdf.set_draw_color(200, 200, 200)  # cinza claro
        pdf.rect(x, y, w, total_height)

        pdf.set_xy(x + padding, y + padding)
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(w - 2 * padding, line_height, txt=user_input6, border=0)

    except Exception as e:
        pdf.add_page()
        pdf.set_xy(col2_w, 12)
        pdf.set_font("Arial", size=14, style='B')
        pdf.multi_cell(
            150,  # largura da célula
            7,  # altura da linha
            txt=f"Erro ao gerar slide 6: {e}",
            align='C'
        )
        print("Erro ao gerar slide 6:", e)

    #________________________________________________________________________Slide 7
    try:
        pdf.show_header = True 
        pdf.add_page()

        col1_w = 80 
        col2_w = 90  
        col3_w = 165  
    
        pdf.set_xy(col2_w, 12)
        pdf.set_font("Arial", size=14, style='B')
        pdf.multi_cell(
            150,  # largura da célula
            7,  # altura da linha
            txt="Acumulados das Últimas 72h e Limiares Críticos do PPDC dos Municípios do Estado de São Paulo",
            align='C'
        )

        mapa_html_inter = 'mapa_html_ppdc'
        transform_html_image(mapa_html_inter)
        tm.sleep(10)
        imgagem_inter = Image.open("imagens/mapa_html_ppdc.png").convert("RGBA")
        background = Image.new("RGB", imgagem_inter.size, (255, 255, 255))  # fundo branco
        background.paste(imgagem_inter, mask=imgagem_inter.split()[3])  # usa canal alpha como máscara
        background.save("imagens/mapa_html_ppdc.jpg", "JPEG", quality=95)

        img = Image.open("imagens/mapa_html_ppdc.jpg")
        width, height = img.size
        cropped_img = img.crop((0, 0, width, height - 1100))
        cropped_img_path = "imagens/mapa_html_ppdc_crop.jpg"
        cropped_img.save(cropped_img_path, "JPEG", quality=95)

        # Adiciona ao PDF
        pdf.image(cropped_img_path, x=10, y=28, w=170)

        pdf.set_xy(58, 108)  # x=20 (imagem), y=120 (abaixo dela)
        pdf.set_font("Arial", size=8, style='I')
        pdf.cell(0, 10, txt="Elaborado pela equipe do SP Águas. Fonte: SIBH", ln=1, link="https://cth.daee.sp.gov.br/sibh/chuva_agora")

        pdf.set_xy(185, 28)
        pdf.set_font("Arial","B", size=12)
        pdf.multi_cell(105, 7, txt="Plano Preventivo de Defesa Civil específico para escorregamentos", align='C')

        x = 185
        y = 42
        w = 105
        padding = 3
        line_height = 7

        cell_height = get_text_height(pdf, user_input7, w - 1.5 * padding, line_height)
        total_height = cell_height + 1.5 * padding

        pdf.set_draw_color(200, 200, 200)  # cinza claro
        pdf.rect(x, y, w, total_height)
        pdf.set_xy(x + padding, y + padding)
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(w - 1.5 * padding, line_height, txt=user_input7, border=0)


        remove_transparency(f"imagens/tabela_ppdc.png")
        pdf.image(f"imagens/tabela_ppdc.png", x=30, y=117, w=238)
    
    except Exception as e:
        pdf.add_page()

        pdf.set_xy(col2_w, 12)
        pdf.set_font("Arial", size=14, style='B')
        pdf.multi_cell(
            150,  # largura da célula
            7,  # altura da linha
            txt=f"Erro ao gerar slide 7: {e}",
            align='C'
        )
        print("Erro ao gerar slide 7:", e)
    #________________________________________________________________________Slide 8
    try:
    
        data_inicial = datetime.today()
        data_inicial_str = data_inicial.strftime('%Y-%m-%d')

        url_inmet = f"https://apivime.inmet.gov.br/COSMO7/SE/prec7dias/{data_inicial_str}H00:00"
        url_imgs = 'https://imgs.somarmeteorologia.com.br/v3/figuras/ncl/somarmet/SE_prec_2.jpg'


        if url == url_inmet:
            fonte = "INMET"
            url_fonte = "https://vime.inmet.gov.br/"
        elif url == url_imgs:
            fonte = "Climatempo"
            url_fonte = "https://imgs.somarmeteorologia.com.br"

        pdf.show_header = True 
        pdf.add_page()

        col1_w = 80 
        col2_w = 120  
        col3_w = 165  
    
        pdf.set_xy(col2_w, 15)
        pdf.set_font("Arial", size=14,style='B')
        pdf.cell(col2_w, txt="Previsão do Tempo", ln=1, align='L')
        pdf.set_font("Arial", size=12)
        
        temp_img_path = "temp_previsao.jpg"
        image.save(temp_img_path)
        
        pdf.image(temp_img_path, x=10, y=32, w=148)
        
        pdf.set_xy(182, 32)
        pdf.set_font("Arial","B", size=12)
        pdf.cell(182, 10, txt="Previsão do Tempo para os dias seguintes", ln=1)

        x = col3_w
        y = 42
        w = 124
        h = 40  # Defina a altura ou calcule com base no texto
        padding = 3
        line_height = 7

        cell_height = get_text_height(pdf, user_input8, w - 2 * padding, line_height)
        total_height = cell_height + 2 * padding

        pdf.set_draw_color(200, 200, 200)  # cinza claro
        pdf.rect(x, y, w, total_height)

        pdf.set_xy(x + padding, y + padding)
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(w - 2 * padding, line_height, txt=user_input8, border=0)
        
        pdf.set_xy(70, 184)  # x=20 (imagem), y=120 (abaixo dela)
        pdf.set_font("Arial", size=10, style='I')
        pdf.cell(0, 10, txt=f"Fonte: {fonte}", ln=1, link=url_fonte)
        
        # Remover arquivo temporário
        import os
        if os.path.exists(temp_img_path):
            os.remove(temp_img_path)
    except Exception as e:
        pdf.add_page()

        pdf.set_xy(col2_w, 12)
        pdf.set_font("Arial", size=14, style='B')
        pdf.multi_cell(
            150,  # largura da célula
            7,  # altura da linha
            txt=f"Erro ao gerar slide 8: {e}",
            align='C'
        )
        print("Erro ao gerar slide 8:", e)
    
    return pdf

def create_pdf_estiagem(user_input1_seca, user_input1, user_input5_seca, user_input6, user_input6_seca , image, user_input8_seca, url):
    # Cria PDF em modo paisagem
    pdf = PDF(orientation='L')

    #Capa
    pdf.show_header = False
    pdf.add_page()

    img = Image.open("Logo Colorido.png").convert("RGBA")
    alpha = 60  # 0 (totalmente transparente) a 255 (opaco)
    img.putalpha(alpha)
    bg = Image.new("RGB", img.size, (255, 255, 255))
    bg.paste(img, mask=img.split()[3])
    bg.save("logo_temp.jpg", "JPEG")
    pdf.image("logo_temp.jpg", x=25, y=-2, w=350)

    pdf.set_xy(10, 85)
    pdf.set_font("Arial", "B", 30)
    pdf.cell(0, 10, "Boletim Diário", ln=True)

    pdf.set_xy(10, 95)
    pdf.set_font("Arial", "B", 15)
    pdf.cell(0, 10, "Sala de Situação São Paulo - SSSP", ln=True)

    data_atual = datetime.today()
    data_anterior = datetime.today() - timedelta(days=1)
    data_atual_str = data_atual.strftime('%d-%m-%Y').replace('-', '/')
    data_anterior_str = data_anterior.strftime('%d-%m-%Y').replace('-', '/')

    pdf.set_xy(10, 102)
    pdf.set_font("Arial", "B", 15)
    pdf.cell(0, 10, f"{data_anterior_str} 07:00 até {data_atual_str} 07:00", ln=True)
    
    imagem_logos = "regua.png"
    pdf.image(imagem_logos, x=165, y=193, w=130)


    #________________________________________________________________Slide 1 Seca
    pdf.show_header = True 
    pdf.add_page()

    col1_w = 80 
    col2_w = 120  
    col3_w = 165  
   
    pdf.set_xy(col2_w, 15)
    pdf.set_font("Arial", size=14,style='B')
    pdf.cell(col2_w, txt="Mapa de dias secos ", ln=1, align='L')
    pdf.set_font("Arial", size=12)

    pdf.set_xy(25, 26)
    pdf.set_font("Arial","B", size=12)
    pdf.cell(0, 10, txt="Dias sem chuva no período de estiagem (01/04 a 30/09)", ln=1)

    mapa_html_dsc = 'mapa_html_dsc'
    transform_html_image(mapa_html_dsc)
    png_path_dsc = f"imagens/{mapa_html_dsc}.png"
    wait_for_file(png_path_dsc)
    tm.sleep(1)
    imgagem_flu = Image.open("imagens/mapa_html_dsc.png").convert("RGBA")
    # background.paste(imgagem_flu, mask=imgagem_flu.getchannel("A"))
    background = Image.new("RGB", imgagem_flu.size, (255, 255, 255))  # fundo branco
    background.paste(imgagem_flu, mask=imgagem_flu.split()[3])  # usa canal alpha como máscara
    background.save("imagens/mapa_html_dsc.jpg", "JPEG", quality=95)
    pdf.image("imagens/mapa_html_dsc.jpg", x=10, y=36, w=136)
    pdf.set_xy(38, 124)  # x=20 (imagem), y=120 (abaixo dela)
    pdf.set_font("Arial", size=8, style='I')
    pdf.cell(0, 10, txt="Elaborado pela equipe do SP Águas. Disponível em: Hidroapp", ln=1, link="https://hidroapp.daee.sp.gov.br/mapa")


    pdf.set_xy(185, 26)
    pdf.set_font("Arial","B", size=12)
    pdf.cell(0, 10, txt="Dias consecutivos sem chuva", ln=1)

    mapa_html_dcsc = 'mapa_html_dcsc'
    transform_html_image(mapa_html_dcsc)
    png_path_dcsc = f"imagens/{mapa_html_dcsc}.png"
    wait_for_file(png_path_dcsc)
    tm.sleep(1)

    imgagem_inter = Image.open("imagens/mapa_html_dcsc.png").convert("RGBA")
    background = Image.new("RGB", imgagem_inter.size, (255, 255, 255))  # fundo branco
    background.paste(imgagem_inter, mask=imgagem_inter.split()[3])  # usa canal alpha como máscara
    background.save("imagens/mapa_html_dcsc.jpg", "JPEG", quality=95)
    pdf.image("imagens/mapa_html_dcsc.jpg", x=150, y=36, w=136)
    pdf.set_xy(177, 125)  # x=150 (imagem), y=120 (abaixo dela)
    pdf.set_font("Arial", size=8, style='I')
    pdf.cell(0, 10, txt="Elaborado pela equipe do SP Águas. Disponível em: Hidroapp", ln=1, link="https://hidroapp.daee.sp.gov.br/mapa")

    x = 10
    y = 142
    w = 278
    padding = 3
    line_height = 7

    pdf.set_xy(x, 132)
    pdf.set_font("Arial","B", size=12)
    pdf.cell(0, 10, txt="Relatos 24h", ln=1)

    cell_height = get_text_height(pdf, user_input1_seca, w - 2 * padding, line_height)
    total_height = cell_height + 2 * padding

    pdf.set_draw_color(200, 200, 200)  # cinza claro
    pdf.rect(x, y, w, total_height)

    pdf.set_xy(x + padding, y + padding)
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(w - 2 * padding, line_height, txt=user_input1_seca, border=0)

    #________________________________________________________________Slide 2 secas
    pdf.show_header = True 
    pdf.add_page()

    col1_w = 80 
    col2_w = 120  
    col3_w = 165  
   
    pdf.set_xy(col2_w, 15)
    pdf.set_font("Arial", size=14,style='B')
    pdf.cell(col2_w, txt="Mapa de dias secos ", ln=1, align='L')
    pdf.set_font("Arial", size=12)

    pdf.set_xy(38, 26)
    pdf.set_font("Arial","B", size=12)
    pdf.cell(0, 10, txt="Dias sem chuva (DSC) por Município", ln=1)
 
    imgagem_dsc = Image.open("imagens/tabela_dsc.png").convert("RGBA")
    # background.paste(imgagem_dsc, mask=imgagem_dsc.getchannel("A"))
    background = Image.new("RGB", imgagem_dsc.size, (255, 255, 255))  # fundo branco
    background.paste(imgagem_dsc, mask=imgagem_dsc.split()[3])  # usa canal alpha como máscara
    background.save("imagens/tabela_dsc.jpg", "JPEG", quality=95)
    pdf.image("imagens/tabela_dsc.jpg", x=10, y=36, w=170)
    pdf.set_xy(62, 124)  # x=20 (imagem), y=120 (abaixo dela)
    pdf.set_font("Arial", size=8, style='I')

    pdf.set_xy(165, 26)
    pdf.set_font("Arial","B", size=12)
    pdf.cell(0, 10, txt="Dias consecutivos sem chuva (DCSC) por Município", ln=1)

    imgagem_dcsc = Image.open("imagens/tabela_dcsc.png").convert("RGBA")
    background = Image.new("RGB", imgagem_dcsc.size, (255, 255, 255))  # fundo branco
    background.paste(imgagem_dcsc, mask=imgagem_dcsc.split()[3])  # usa canal alpha como máscara
    background.save("imagens/tabela_dcsc.jpg", "JPEG", quality=95)
    pdf.image("imagens/tabela_dcsc.jpg", x=150, y=36, w=170)
    
    x = 10
    y = 142
    w = 278
    padding = 3
    line_height = 7

    pdf.set_xy(117, 97)
    pdf.set_font("Arial","B", size=12)
    pdf.cell(0, 10, txt="% de cidades com DCSC por UGRHI", ln=1)

    imgagem_inter = Image.open("imagens/grafico_dcsc_ugrhi.png").convert("RGBA")
    background = Image.new("RGB", imgagem_inter.size, (255, 255, 255))  # fundo branco
    background.paste(imgagem_inter, mask=imgagem_inter.split()[3])  # usa canal alpha como máscara
    background.save("imagens/grafico_dcsc_ugrhi.jpg", "JPEG", quality=95)
    pdf.image("imagens/grafico_dcsc_ugrhi.jpg", x=25, y=105, w=270)



    #________________________________________________________________Slide 1
    pdf.show_header = True 
    pdf.add_page()

    col1_w = 80 
    col2_w = 120  
    col3_w = 165  
   
    pdf.set_xy(col2_w, 15)
    pdf.set_font("Arial", size=14,style='B')
    pdf.cell(col2_w, txt="Dados Pluviometria", ln=1, align='L')
    pdf.set_font("Arial", size=12)

    pdf.set_xy(38, 26)
    pdf.set_font("Arial","B", size=12)
    pdf.cell(0, 10, txt="Acumulado de chuva das ultimas 24h", ln=1)

    mapa_html_flu = 'mapa_html_flu'
    transform_html_image(mapa_html_flu)
    png_path_flu = f"imagens/{mapa_html_flu}.png"
    wait_for_file(png_path_flu)
    tm.sleep(1)

    imgagem_flu = Image.open("imagens/mapa_html_flu.png").convert("RGBA")
    # background.paste(imgagem_flu, mask=imgagem_flu.getchannel("A"))
    background = Image.new("RGB", imgagem_flu.size, (255, 255, 255))  # fundo branco
    background.paste(imgagem_flu, mask=imgagem_flu.split()[3])  # usa canal alpha como máscara
    background.save("imagens/mapa_html_flu.jpg", "JPEG", quality=95)
    pdf.image("imagens/mapa_html_flu.jpg", x=10, y=36, w=136)
    pdf.set_xy(62, 124)  # x=20 (imagem), y=120 (abaixo dela)
    pdf.set_font("Arial", size=8, style='I')
    pdf.cell(0, 10, txt="Fonte: Chuva agora - SIBH", ln=1, link="https://cth.daee.sp.gov.br/sibh/chuva_agora")


    pdf.set_xy(165, 26)
    pdf.set_font("Arial","B", size=12)
    pdf.cell(0, 10, txt="Interpolação dos pluviômetros a partir do método IDW", ln=1)

    mapa_html_inter = 'mapa_html_inter'
    transform_html_image(mapa_html_inter)
    png_path_inter= f"imagens/{mapa_html_inter}.png"
    wait_for_file(png_path_inter)
    tm.sleep(1)

    imgagem_inter = Image.open("imagens/mapa_html_inter.png").convert("RGBA")
    background = Image.new("RGB", imgagem_inter.size, (255, 255, 255))  # fundo branco
    background.paste(imgagem_inter, mask=imgagem_inter.split()[3])  # usa canal alpha como máscara
    background.save("imagens/mapa_html_inter.jpg", "JPEG", quality=95)
    pdf.image("imagens/mapa_html_inter.jpg", x=150, y=36, w=136)
    pdf.set_xy(152, 125)  # x=150 (imagem), y=120 (abaixo dela)
    pdf.set_font("Arial", size=8, style='I')
    pdf.multi_cell(135, 5, txt="Elaborado pela equipe técnica da Sala de Situação São Paulo (SSSP). Parâmetros: Potência=0.02, Suavização=0.02 e Raio=0.5.", align='C')
    
    x = 10
    y = 142
    w = 278
    padding = 3
    line_height = 7

    pdf.set_xy(x, 132)
    pdf.set_font("Arial","B", size=12)
    pdf.cell(0, 10, txt="Relatos 24h", ln=1)

    cell_height = get_text_height(pdf, user_input1, w - 2 * padding, line_height)
    total_height = cell_height + 2 * padding

    pdf.set_draw_color(200, 200, 200)  # cinza claro
    pdf.rect(x, y, w, total_height)

    pdf.set_xy(x + padding, y + padding)
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(w - 2 * padding, line_height, txt=user_input1, border=0)

    #________________________________________________________________Slide 2
    pdf.show_header = True 
    pdf.add_page()

    col1_w = 80 
    col2_w = 120  
    col3_w = 165  

    pdf.set_xy(col2_w, 15)
    pdf.set_font("Arial", size=14,style='B')
    pdf.cell(col2_w, txt="Dados Pluviometria", ln=1, align='L')
    pdf.set_font("Arial", size=12)

    pdf.set_xy(10, 25)
    pdf.set_font("Arial","B", size=12)
    pdf.multi_cell(135, 7, txt="Municípios com os maiores acumulados de chuvas observadas nas últimas 24h (mm) (Rede Telemétrica)", align='C')
    imgagem_tabela = Image.open("imagens/tabela_chuva.png").convert("RGBA")
    background = Image.new("RGB", imgagem_tabela.size, (255, 255, 255))
    background.paste(imgagem_tabela, mask=imgagem_tabela.split()[3])  # usa canal alpha como máscara
    background.save("imagens/tabela_chuva.jpg", "JPEG", quality=95)
    pdf.image("imagens/tabela_chuva.jpg", x=6, y=38, w=153)
    
    pdf.set_xy(10, 113)
    pdf.set_font("Arial", size=10)
    texto = (
        "1- Máximo Registrado - Volume máximo (mm) registrado por um posto pluviométrico do município.\n"
        "2- Média Registrada - Soma do Volume (mm) de todos os postos do município / n° de postos.\n"
        "3- Acumulado média mês - Soma da média (mm) registrada do primeiro dia do mês até o momento.\n"
        "4- Histórico mensal - Volume médio mensal calculado a partir da série histórica disponível."
    )
    pdf.multi_cell(135, 5, txt=texto)

    pdf.set_xy(155, 26)
    pdf.set_font("Arial","B", size=12)
    pdf.multi_cell(135, 6, txt='Comparação de Precipitação por Município', align='C')
    pdf.image("imagens/grafico_chuva.png", x=155, y=32, w=121)

    pdf.set_xy(155, 115)
    pdf.set_font("Arial","B", size=12)
    pdf.multi_cell(135, 6, txt='Chuva média acumulada por UGRHI', align='C')
    pdf.image("imagens/grafico_chuva2.png", x=155, y=120, w=120)

    #________________________________________________________________________Slide 5 Seca 
    pdf.show_header = True 
    pdf.add_page()

    col1_w = 80 
    col2_w = 120  
    col3_w = 165  
   
    pdf.set_xy(col2_w, 15)
    pdf.set_font("Arial", size=14,style='B')
    pdf.cell(col2_w, txt="Dados Fluviometria - Estiagem", ln=1, align='L')
    pdf.set_font("Arial", size=12)

    mapa_slide5_seca = "mapa_slide5_seca"
    transform_html_image(mapa_slide5_seca)
    png_path5_seca= f"imagens/{mapa_slide5_seca}.png"
    wait_for_file(png_path5_seca)
    tm.sleep(1)

    imgagem_html_5 = Image.open("imagens/mapa_slide5_seca.png").convert("RGBA")
    # background.paste(imgagem_flu, mask=imgagem_flu.getchannel("A"))
    background = Image.new("RGB", imgagem_html_5.size, (255, 255, 255))  # fundo branco
    background.paste(imgagem_html_5, mask=imgagem_html_5.split()[3])  # usa canal alpha como máscara
    background.save("imagens/mapa_slide5_seca.jpg", "JPEG", quality=95)
    pdf.image("imagens/mapa_slide5_seca.jpg", x=40, y=25, w=210)
    pdf.set_xy(115, 158)  # x=20 (imagem), y=120 (abaixo dela)
    pdf.set_font("Arial", size=8, style='I')
    pdf.cell(0, 10, txt="Fonte: Chuva agora - SIBH", ln=1, link="https://cth.daee.sp.gov.br/sibh/chuva_agora")

    x = 10
    y = 170
    w = 270
    padding = 3
    line_height = 7

    pdf.set_xy(x, 160)
    pdf.set_font("Arial","B", size=12)
    pdf.cell(0, 10, txt="Análise das redes Telemétrica", ln=1)

    cell_height = get_text_height(pdf, user_input5_seca, w - 2 * padding, line_height)
    total_height = cell_height + 2 * padding

    pdf.set_draw_color(200, 200, 200)  # cinza claro
    pdf.rect(x, y, w, total_height)

    pdf.set_xy(x + padding, y + padding)
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(w - 2 * padding, line_height, txt=user_input5_seca, border=0)



    #________________________________________________________________________Slide 6
    pdf.show_header = True 
    pdf.add_page()

    col1_w = 80 
    col2_w = 120  
    col3_w = 165  
   
    pdf.set_xy(col2_w, 15)
    pdf.set_font("Arial", size=14,style='B')
    pdf.cell(col2_w, txt="Sistema Produtores da RMSP", ln=1, align='L')
    pdf.set_font("Arial", size=12)

    pdf.image("results/imagem_rmsp.png", x=15, y=25, w=265)

    pdf.set_xy(120, 189)  # x=20 (imagem), y=120 (abaixo dela)
    pdf.set_font("Arial", size=8, style='I')
    pdf.cell(0, 10, txt="Fonte: SSD-Sistemas Produtores", ln=1, link="https://cth.daee.sp.gov.br/ssdsp/")


    pdf.show_header = True 
    pdf.add_page()

    col1_w = 80 
    col2_w = 120  
    col3_w = 165  
   
    pdf.set_xy(col2_w, 15)
    pdf.set_font("Arial", size=14,style='B')
    pdf.cell(col2_w, txt="Sistema Produtores da RMSP", ln=1, align='L')
    pdf.set_font("Arial", size=12)

    pdf.set_xy(10, 26)
    pdf.set_font("Arial","B", size=12)
    pdf.multi_cell(135, 7, txt="Comparação entre volume atual x volume no ano anterior (%)", align='C')
    remove_transparency(f"imagens/grafico_rmsp.png")
    pdf.image(f"imagens/grafico_rmsp.png", x=8, y=32, w=134)

    pdf.set_xy(150, 26)
    pdf.set_font("Arial","B", size=12)
    pdf.multi_cell(135, 7, txt="Volume dos Sistemas Produtores (Sabesp)", align='C')
    remove_transparency(f"imagens/tabela_rmsp.png")
    pdf.image(f"imagens/tabela_rmsp.png", x=147, y=32, w=160)


    x = 10
    y = 150
    w = 270
    padding = 3
    line_height = 7

    pdf.set_xy(x, 140)
    pdf.set_font("Arial","B", size=12)
    pdf.cell(0, 10, txt="Análise dos Sistemas Produtores", ln=1)

    cell_height = get_text_height(pdf, user_input6, w - 2 * padding, line_height)
    total_height = cell_height + 2 * padding

    pdf.set_draw_color(200, 200, 200)  # cinza claro
    pdf.rect(x, y, w, total_height)

    pdf.set_xy(x + padding, y + padding)
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(w - 2 * padding, line_height, txt=user_input6, border=0)


    #________________________________________________________________________Slide 6 seca
    pdf.show_header = True 
    pdf.add_page()

    col1_w = 80 
    col2_w = 120 
    col3_w = 165  
   
    pdf.set_xy(col2_w, 12)
    pdf.set_font("Arial", size=14, style='B')
    pdf.cell(col2_w, txt="Sistema Alto Tietê - Estiagem", ln=1, align='L')

    pdf.set_xy(50, 26)
    pdf.set_font("Arial","B", size=12)
    pdf.multi_cell(0, 7, txt="Dados do sistema Alto Tietê", align='L')
    remove_transparency(f"imagens/tabela_alto_tiete.png")
    pdf.image(f"imagens/tabela_alto_tiete.png", x=8, y=37, w=150)
    pdf.set_xy(59, 100)  # x=20 (imagem), y=120 (abaixo dela)
    pdf.set_font("Arial", size=8, style='I')
    pdf.cell(0, 10, txt="Fonte: SSSD Alto Tietê - CTH - DAEE", ln=1, link="https://cth.daee.sp.gov.br/ssdsp/Sistema/AltoTiete")

    data_inicial = datetime.today()
    data_str = data_inicial.strftime('%Y-%m-%d')
    pdf.set_xy(150, 26)
    pdf.set_font("Arial","B", size=12)
    pdf.multi_cell(0, 7, txt="Diagrama unifiliar do Alto Tietê", align='C')
    pdf.image(f"results/imagem_alto_tiete_{data_str}.png", x=155, y=32, w=140)
    pdf.set_xy(200, 100)  # x=20 (imagem), y=120 (abaixo dela)
    pdf.set_font("Arial", size=8, style='I')
    pdf.cell(0, 10, txt="Fonte: SSSD Alto Tietê - CTH - DAEE", ln=1, link="https://cth.daee.sp.gov.br/ssdsp/Sistema/AltoTiete")


    x = 10
    y = 150
    w = 270
    padding = 3
    line_height = 7

    pdf.set_xy(x, 140)
    pdf.set_font("Arial","B", size=12)
    pdf.cell(0, 10, txt= "Análise do Sistema Produtor - Alto Tietê", ln=1)
   
    cell_height = get_text_height(pdf, user_input6_seca, w - 2 * padding, line_height)
    total_height = cell_height + 2 * padding

    pdf.set_draw_color(200, 200, 200)  # cinza claro
    pdf.rect(x, y, w, total_height)

    pdf.set_xy(x + padding, y + padding)
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(w - 2 * padding, line_height, txt=user_input6_seca, border=0)



    #________________________________________________________________________Slide 8

    data_inicial = datetime.today()
    data_inicial_str = data_inicial.strftime('%Y-%m-%d')

    url_inmet = f"https://apivime.inmet.gov.br/COSMO7/SE/prec7dias/{data_inicial_str}H00:00"
    url_imgs = 'https://imgs.somarmeteorologia.com.br/v3/figuras/ncl/somarmet/SE_prec_2.jpg'


    if url == url_inmet:
        fonte = "INMET"
        url_fonte = "https://vime.inmet.gov.br/"
    elif url == url_imgs:
        fonte = "Climatempo"
        url_fonte = "https://imgs.somarmeteorologia.com.br"


    pdf.show_header = True 
    pdf.add_page()

    col1_w = 80 
    col2_w = 120  
    col3_w = 165  
   
    pdf.set_xy(col2_w, 15)
    pdf.set_font("Arial", size=14,style='B')
    pdf.cell(col2_w, txt="Pentada", ln=1, align='L')
    pdf.set_font("Arial", size=12)
    
    temp_img_path = "imagens/temp_pentada.jpg"
    image.save(temp_img_path)
    
    pdf.image(temp_img_path, x=10, y=32, w=148)
    
    pdf.set_xy(182, 32)
    pdf.set_font("Arial","B", size=12)
    pdf.cell(182, 10, txt="Previsão do Tempo para os dias seguintes", ln=1)

    x = col3_w
    y = 42
    w = 120
    padding = 3
    line_height = 7

    cell_height = get_text_height(pdf, user_input8_seca, w - 2 * padding, line_height)
    total_height = cell_height + 2 * padding

    pdf.set_draw_color(200, 200, 200)  # cinza claro
    pdf.rect(x, y, w, total_height)

    pdf.set_xy(x + padding, y + padding)
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(w - 2 * padding, line_height, txt=user_input8_seca, border=0)
    
    pdf.set_xy(70, 184)  # x=20 (imagem), y=120 (abaixo dela)
    pdf.set_font("Arial", size=10, style='I')
    pdf.cell(0, 10, txt=f"Fonte: {fonte}", ln=1, link=url_fonte)
    
    if os.path.exists(temp_img_path):
        os.remove(temp_img_path)
    
    return pdf


def refresh_viwe():
    query = 'REFRESH MATERIALIZED VIEW station_rainfall_accum_month;'

    try:
        cur = conection_postgres()
        conn = cur.connection
        cur.execute(query)
        conn.commit()  

    except Exception as e:
        print(f"Erro ao executar a query: {e}")

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()



def gerar_mapa_chuva_shapefile(get_data, data_shapefile, arquivo, excluir_prefixos):

    data_inicial = datetime.today()
    hora_inicial = time(7, 0)
    data_hora_inicial = datetime.combine(data_inicial, hora_inicial)
    data_inicial_str = data_hora_inicial.strftime('%Y-%m-%d')
    hora_inicial_str = data_hora_inicial.strftime('%H:%M')

    horas = 24

    data_hora_final = data_hora_inicial - timedelta(hours=horas)
    date_time_id = data_hora_inicial.strftime("%Y%m%d%H%M")

    url = f'https://cth.daee.sp.gov.br/sibh/api/v2/measurements/now?station_type_id=2&hours=24&from_date={data_inicial_str}T{hora_inicial_str}&show_all=true&public=true'
    estatistica_desejada = "mean"

    minx, miny, maxx, maxy = get_data.total_bounds

    get_data.to_file(data_shapefile)

    # Obtendo dados da API
    response = requests.get(url)
    data = response.json()

    # Extraindo coordenadas e valores
    stations = [
        (item["prefix"], float(item["latitude"]), float(item["longitude"]), item["value"])
        for item in data["measurements"]
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
    
    data_stats.to_file(f"./results/acumulado_24_mun_{data_hora_final.strftime('%Y-%m-%d')}.shp", driver="ESRI Shapefile")
   
def definir_cor(valor):
    if valor < 10:
        return "#16c995"
    elif 10 <= valor < 30:
        return "#fcb900"
    elif 30 <= valor < 70:
        return "#ff7b00"
    else:
        return "#f74f78"

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
        return 'Atenção'
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

def iniciar_chrome_com_diretorio_unico():
    # Cria diretório temporário exclusivo
    unique_user_data_dir = tempfile.mkdtemp(prefix="selenium_profile_")

    # Configura opções do Chrome
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")  # Usar 'new' evita erros com a versão atual do Chrome
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1300,2000")
    options.add_argument("--disable-web-security")
    options.add_argument(f"--user-data-dir={unique_user_data_dir}")
    options.add_argument("--force-device-scale-factor=1")

    # ✅ Flags adicionais importantes para Docker/Linux
    options.add_argument("--allow-running-insecure-content")
    options.add_argument("--disable-features=IsolateOrigins,site-per-process")
    options.add_argument("--disable-site-isolation-trials")

    # Inicia o ChromeDriver
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(options=options, service=service)

    return driver, unique_user_data_dir

def capturar_ipmet_bkp():
    driver, dir_path = iniciar_chrome_com_diretorio_unico()
    try:
        usuario = os.environ.get('IPMET_USERNAME')
        senha = os.environ.get('IPMET_PASSWORD')
        # url = f"https://www.ipmetradar.com.br/restrito/2login.php?username={usuario}&senha={senha}&tipo_acesso=ip"
        url="https://www.ipmetradar.com.br/2mobileGis.php"

        driver.get(url)

        wait = WebDriverWait(driver, 15)  # Espera até 15 segundos
        iframe = wait.until(EC.presence_of_element_located((By.TAG_NAME, "iframe")))

        driver.switch_to.frame(iframe)
        driver.implicitly_wait(5)

        select_element = driver.find_element(By.CSS_SELECTOR, "#layer-select")
        select_element.click()
        tm.sleep(3)
        select = Select(select_element)
        select.select_by_value("acum24h")
        tm.sleep(14)
        select_element.click()

        select_button = driver.find_element(By.CSS_SELECTOR, "button.ol-zoom-out")
        select_button.click()

        tm.sleep(3)

        driver.save_screenshot("screenshot_ipmet.png")

        img = Image.open("screenshot_ipmet.png")
        imagem_recortada = img.crop((170, 270, 950, 620)) #esquerda, cima, direita, baixo
        data_inicial = datetime.today()
        data_str = data_inicial.strftime('%Y-%m-%d')

        output_path = os.path.join("results", f"imagem_ipmet_{data_str}.png")
        imagem_recortada.save(output_path)

        return imagem_recortada, url
    
    finally:
        driver.quit()
        shutil.rmtree(dir_path, ignore_errors=True)

def capturar_ipmet():
    driver, dir_path = iniciar_chrome_com_diretorio_unico()
    try:
        url = "https://www.ipmetradar.com.br/2mobileGis.php"
        driver.get(url)

        wait = WebDriverWait(driver, 30)  # ✅ Aumentar timeout

        # ✅ Esperar iframe estar visível, não só presente
        iframe = wait.until(EC.visibility_of_element_located((By.TAG_NAME, "iframe")))
        driver.switch_to.frame(iframe)
        tm.sleep(5)

        # ✅ Esperar o select estar clicável antes de interagir
        select_element = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#layer-select")))
        select = Select(select_element)
        select.select_by_value("acum24h")

        # ✅ Após mudar o select, esperar algum elemento do mapa re-renderizar
        # Substitua ".ol-layer canvas" pelo seletor correto do mapa se necessário
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".ol-layer canvas")))
        except:
            pass  # Se não achar, continua com sleep mesmo assim

        tm.sleep(20)  # ✅ Aumentar — Linux sem GPU renderiza mais devagar

        select_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.ol-zoom-out")))
        select_button.click()

        tm.sleep(10)  # ✅ Dar tempo após zoom
        # image_screenshot = "screenshot_ipmet.png"
        # if os.path.exists(image_screenshot):
        #     os.remove(image_screenshot)


        # ✅ Salvar debug screenshot para diagnosticar no servidor
        driver.save_screenshot("results/screenshot_ipmet.png")

        img = Image.open("results/screenshot_ipmet.png")

        imagem_recortada = img.crop((170, 270, 950, 620))
        data_str = datetime.today().strftime('%Y-%m-%d')
        output_path = os.path.join("results", f"imagem_ipmet_{data_str}.png")
        imagem_recortada.save(output_path)

        return imagem_recortada, url

    finally:
        driver.quit()
        shutil.rmtree(dir_path, ignore_errors=True)

def capturar_saisp():
    driver, dir_path = iniciar_chrome_com_diretorio_unico()
    try:
        data_anterior = datetime.today() - timedelta(days=1)
        data_anterior_str = data_anterior.strftime('%d-%m-%Y').replace('-', '/')
        data = data_anterior.strftime('%Y%m%d')

        usuario = os.environ.get('SAISP_USERNAME')
        senha = os.environ.get('SAISP_PASSWORD')
        password_encoded = urllib.parse.quote(senha)

        url = f"https://{usuario}:{password_encoded}@www.saisp.br/geral/processo.jsp?comboFiltroGrupo=&PRODUTO=636&OVLCODE=EPI&dataInicial={data_anterior_str}+07%3A00&WHICHCODE=0&autoUpdate=1&STEP=&DI={data}0700&DF="

        driver.get(url)
        driver.implicitly_wait(35)
        driver.save_screenshot("screenshot_saisp.png")

        img = Image.open("screenshot_saisp.png")
        imagem_recortada = img.crop((500, 51, 972, 533)) #esquerda, cima, direita, baixo
        imagem_borda = ImageOps.expand(imagem_recortada, border=2, fill='black')

        data_inicial = datetime.today()
        data_str = data_inicial.strftime('%Y-%m-%d')
        output_path = os.path.join("results", f"imagem_saisp_{data_str}.png")
        imagem_borda.save(output_path)

        return imagem_borda, url

    finally:
        driver.quit()
        shutil.rmtree(dir_path, ignore_errors=True)

def capturar_ssd():
    driver, dir_path = iniciar_chrome_com_diretorio_unico()
    try:
        data_anterior = datetime.today() - timedelta(days=1)
        data_anterior_str = data_anterior.strftime('%d-%m-%Y').replace('-', '/')
        data = data_anterior.strftime('%Y%m%d')

        usuario = os.environ.get('SAISP_USERNAME')
        senha = os.environ.get('SAISP_PASSWORD')
        password_encoded = urllib.parse.quote(senha)

        url = f"https://{usuario}:{password_encoded}@www.saisp.br/geral/processo.jsp?comboFiltroGrupo=&PRODUTO=636&OVLCODE=EPI&dataInicial={data_anterior_str}+07%3A00&WHICHCODE=0&autoUpdate=1&STEP=&DI={data}0700&DF="

        driver.get(url)
        driver.implicitly_wait(35)
        driver.save_screenshot("screenshot_saisp.png")

        img = Image.open("screenshot_saisp.png")
        imagem_recortada = img.crop((500, 51, 972, 533)) #esquerda, cima, direita, baixo
        imagem_borda = ImageOps.expand(imagem_recortada, border=2, fill='black')
        return imagem_borda, url

    finally:
        driver.quit()
        shutil.rmtree(dir_path, ignore_errors=True)

def get_sabesp_api_dashboard(data_atual_str, data_ano_anterior_str, data_7dias_str, data_14dias_str, data_21dias_str):

    url_ano_atual = f"https://mananciais-sabesp.fcth.br/api/Mananciais/Boletins/Mananciais/{data_atual_str}"
    response = requests.get(url_ano_atual, verify=False, timeout=120)

    if response.status_code == 200:

        data = response.json()
        print('response ano atual', datetime.now())
        if 'ReturnObj' in data and 'dadosSistemas' in data['ReturnObj']:

            json_data = data['ReturnObj']
            path = os.path.join("results", "sabesp_sistemas_all_data.json")
            print(path)

            with open(path, "w", encoding="utf-8") as f:
                json.dump(json_data, f, indent=4, ensure_ascii=False)

        else:
            print("A chave 'dadosSistemas' não foi encontrada dentro de 'ReturnObj' ou 'ReturnObj' está vazio.")
    else:
        print(f"Erro na requisição ano atual. Status Code: {response.status_code}")
    
    url_ano_anteior = f"https://mananciais-sabesp.fcth.br/api/Mananciais/Boletins/Mananciais/{data_ano_anterior_str}"
    response_1 = requests.get(url_ano_anteior, verify=False, timeout=120)
    if response_1.status_code == 200:

        data_1 = response_1.json()

        if 'ReturnObj' in data_1 and 'dadosSistemas' in data_1['ReturnObj']:

            json_data_1 = data_1['ReturnObj']
            path = os.path.join("results", "sabesp_sistemas_all_data_anoanterior.json")
            print(path)

            with open(path, "w", encoding="utf-8") as f:
                json.dump(json_data_1, f, indent=4, ensure_ascii=False)

        else:
            print("A chave 'dadosSistemas' não foi encontrada dentro de 'ReturnObj' ou 'ReturnObj' está vazio.")
    else:
        print(f"Erro na requisição ano anterior. Status Code: {response.status_code}")

    url_7_dias = f"https://mananciais-sabesp.fcth.br/api/Mananciais/Boletins/Mananciais/{data_7dias_str}"
    response_7 = requests.get(url_7_dias, verify=False, timeout=120)

    if response_7.status_code == 200:

        data_7dias = response_7.json()
        print('response ano anterior', datetime.now())
        if 'ReturnObj' in data_7dias and 'dadosSistemas' in data_7dias['ReturnObj']:

            json_data_7dias = data_7dias['ReturnObj']
            path = os.path.join("results", "sabesp_sistemas_all_data_7dias.json")

            with open(path, "w", encoding="utf-8") as f:
                json.dump(json_data_7dias, f, indent=4, ensure_ascii=False)
                
        else:
            print("A chave 'dadosSistemas' não foi encontrada dentro de 'ReturnObj' ou 'ReturnObj' está vazio.")
    else:
        print(f"Erro na requisição ano anterior. Status Code: {response.status_code}")

    url_14_dias = f"https://mananciais-sabesp.fcth.br/api/Mananciais/Boletins/Mananciais/{data_14dias_str}"
    response_14 = requests.get(url_14_dias, verify=False, timeout=120)

    if response_14.status_code == 200:

        data_14dias = response_14.json()
        print('response ano anterior', datetime.now())
        if 'ReturnObj' in data_14dias and 'dadosSistemas' in data_14dias['ReturnObj']:
            json_data_14dias = data_14dias['ReturnObj']
            path = os.path.join("results", "sabesp_sistemas_all_data_14dias.json")

            with open(path, "w", encoding="utf-8") as f:
                json.dump(json_data_14dias, f, indent=4, ensure_ascii=False)
            
        else:
            print("A chave 'dadosSistemas' não foi encontrada dentro de 'ReturnObj' ou 'ReturnObj' está vazio.")
    else:
        print(f"Erro na requisição ano anterior. Status Code: {response.status_code}")

    url_21_dias = f"https://mananciais-sabesp.fcth.br/api/Mananciais/Boletins/Mananciais/{data_21dias_str}"
    response_21 = requests.get(url_21_dias, verify=False, timeout=120)

    if response_21.status_code == 200:

        data_21dias = response_21.json()
        if 'ReturnObj' in data and 'dadosSistemas' in data_14dias['ReturnObj']:
            json_data_21dias = data_21dias['ReturnObj']
            path = os.path.join("results", "sabesp_sistemas_all_data_21dias.json")

            with open(path, "w", encoding="utf-8") as f:
                json.dump(json_data_21dias, f, indent=4, ensure_ascii=False)

        else:
            print("A chave 'dadosSistemas' não foi encontrada dentro de 'ReturnObj' ou 'ReturnObj' está vazio.")
    else:
        print(f"Erro na requisição ano anterior. Status Code: {response.status_code}")

def fetch_and_save_json(data_str, filename):
    print(data_str, filename)
    url = f"https://mananciais-sabesp.fcth.br/api/Mananciais/Boletins/Mananciais/{data_str}"
    try:
        response = requests.get(url, verify=False, timeout=120)
        if response.status_code == 200:
            print("retornou_response")
            data = response.json()
            if 'ReturnObj' in data and 'dadosSistemas' in data['ReturnObj']:
                path = os.path.join("results", filename)
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data['ReturnObj'], f, indent=4, ensure_ascii=False)
                print(f"{filename} salvo com sucesso.")
            else:
                print(f"'dadosSistemas' não encontrado para {data_str}.")
        else:
            print(f"Erro {response.status_code} para {data_str}.")
    except requests.exceptions.RequestException as e:
        print(f"Erro na requisição {data_str}: {e}")
        
def get_sabesp_api(data_atual_str, data_ano_anterior_str):

    url_ano_atual = f"https://mananciais-sabesp.fcth.br/api/Mananciais/Boletins/Mananciais/{data_atual_str}"
    print(url_ano_atual)
    response = requests.get(url_ano_atual, verify=False)

    if response.status_code == 200:

        data = response.json()
        print('response ano atual', datetime.now())
        if 'ReturnObj' in data and 'dadosSistemas' in data['ReturnObj']:
            df_sistemas_ano_atual = pd.DataFrame(data['ReturnObj']['dadosSistemas'])
        else:
            print("A chave 'dadosSistemas' não foi encontrada dentro de 'ReturnObj' ou 'ReturnObj' está vazio.")
    else:
        print(f"Erro na requisição ano atual. Status Code: {response.status_code}")
    print("Url ano anterior", datetime.now())
    url_ano_anteior = f"https://mananciais-sabesp.fcth.br/api/Mananciais/Boletins/Mananciais/{data_ano_anterior_str}"
    response = requests.get(url_ano_anteior, verify=False)

    if response.status_code == 200:

        data = response.json()
        print('response ano anterior', datetime.now())
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
        "SIM": 459
    }

    df_sistemas = pd.DataFrame(list(dados_sistema.items()), columns=["Sistema", "SistemaId"])


    url_sim = f'https://cth.daee.sp.gov.br/ssdsp/api-private/TimeSeries/459/Data/{data_ano_anterior_str}/{data_atual_str}'
    response = requests.get(url_sim, verify=False)

    if response.status_code == 200:
        data = response.json()
        if "dataCollection" in data:
            df_sim_atual_all = pd.DataFrame(data["dataCollection"])
            df_sim_atual = df_sim_atual_all.copy()
            df_sim_atual['SistemaId'] = 459

            valor_atual = df_sim_atual_all.loc[df_sim_atual_all['dateTime'] == data_atual_str, 'value'].iloc[0]
            valor_ano_anterior = df_sim_atual_all.loc[df_sim_atual_all['dateTime'] == data_ano_anterior_str, 'value'].iloc[0]

            df_sim_atual["VolumePorcentagem"] = valor_atual
            df_sim_atual["Volume Ano Anterior (%)"] = valor_ano_anterior

            df_sim_atual = df_sim_atual[df_sim_atual['dateTime'] == data_atual_str]
            df_sim_atual = df_sim_atual.drop(columns={"deliveredAt", "value"})


    merged_data = pd.concat([merged_data, df_sim_atual], ignore_index=True)
    merged_data_sistemas = pd.merge(merged_data, df_sistemas, on='SistemaId', how='left')
    merged_data_sistemas = merged_data_sistemas.dropna(subset=['Sistema'])

    merged_data_sistemas['Diferença Vol. Anual (%)'] = merged_data_sistemas['VolumePorcentagem'] - merged_data_sistemas['Volume Ano Anterior (%)']

    merged_data_sistemas = merged_data_sistemas.rename(columns={'VolumePorcentagem': 'VolumeAtual (%)', 'Precipitacao': 'Chuva (mm)', 'PrecipitacaoAcumuladaNoMes': 'Acumulado no Mês (mm)', 'PMLTMensal':'Média Histórica (mm)'})

    merged_data_sistemas = merged_data_sistemas[['Sistema', 'VolumeAtual (%)', 'Volume Ano Anterior (%)', 'Diferença Vol. Anual (%)', 'Chuva (mm)', 'Acumulado no Mês (mm)', 'Média Histórica (mm)']]

    cols = ['Chuva (mm)', 'Acumulado no Mês (mm)', 'Média Histórica (mm)']

    # Arredonda primeiro
    merged_data_sistemas[cols] = merged_data_sistemas[cols].round(1)

    # Formata cada elemento como string
    merged_data_sistemas[cols] = merged_data_sistemas[cols].applymap(lambda x: f'{x:.1f}' if pd.notna(x) else '-')

    data_atual_str = datetime.today().strftime("%Y-%m-%d")
    merged_data_sistemas["Data"] = data_atual_str

    caminho_arquivo_json = os.path.join("results", f"sabesp_sistemas.json")


    merged_data_sistemas.to_json(caminho_arquivo_json, orient='records', force_ascii=False, indent=2)

def get_sabesp_api_resumo(data_atual_str, data_ano_anterior_str):

    key = os.environ.get('KEY')
    value = os.environ.get('VALUE')
    headers = {key: value}

    sistema_sabesp = {
        "cantareira": "Cantareira",
        "alto-tiete": "Alto Tietê",
        "guarapiranga": "Guarapiranga",
        "cotia": "Cotia",
        "rio-grande": "Rio Grande",
        "rio-claro": "Rio Claro",
        "sao-lourenco": "São Lourenço"
    }

    df_sistemas_sabesp = pd.DataFrame(list(sistema_sabesp.items()), columns=["Sistema_sabesp", "Sistema"])

    atual_all_data=[]
    for _, sistema in df_sistemas_sabesp.iterrows():
        id = sistema["Sistema_sabesp"]

        url_sabesp = f"https://ssdapi.sabesp.com.br/api/ssd/sistemas/{id}/dados/{data_ano_anterior_str}/{data_atual_str}"
        response_sabesp = requests.get(url_sabesp, headers=headers)

        if response_sabesp.status_code == 200:
            dados_sabesp = response_sabesp.json()
            if "data" in dados_sabesp:
                df_dados_sabesp = pd.DataFrame(dados_sabesp["data"])
                df_dados_sabesp['Sistema'] = sistema["Sistema"]
                df_dados_sabesp["data"] = pd.to_datetime(df_dados_sabesp["data"])
                df_dados_sabesp["data"] = df_dados_sabesp["data"].dt.strftime("%Y-%m-%d")

                df_atual_all = df_dados_sabesp.copy()

                filtro = df_atual_all.loc[df_atual_all['data'] == data_ano_anterior_str, 'volumeOperacional_porcentagem']
                valor_ano_anterior = filtro.iloc[0] if not filtro.empty else None
                df_atual_all["Volume Ano Anterior (%)"] = valor_ano_anterior

                # pega a linha do dia atual, senão última disponível
                if (df_atual_all["data"] == data_atual_str).any():
                    linha_atual = df_atual_all.loc[df_atual_all["data"] == data_atual_str].sort_index().tail(1).copy()
                    linha_atual["Data"] = data_atual_str
                else:
                    linha_atual = df_atual_all.tail(1).copy()
                    linha_atual["Data"] = df_atual_all["data"].tail(1).iloc[0] 
                linha_atual = linha_atual.rename(columns={"volumeOperacional_porcentagem": "Volume Atual (%)"})

                atual_all_data.append(linha_atual)

    df_final_all_data_sabesp= pd.concat(atual_all_data, ignore_index=True)
    
    today = datetime.today()
    data_str = today.strftime("%a %b %d %Y %H:%M:%S GMT-0300 (Horário Padrão de Brasília)")

    try:
        data_anterior = today.replace(year=today.year - 1)
    except ValueError:
        # Trata 29/02
        data_anterior = today.replace(month=2, day=28, year=today.year - 1)

    data_str_anterior = data_anterior.strftime(
        "%a %b %d %Y %H:%M:%S GMT-0300 (Horário Padrão de Brasília)"
    )

    url_ana_atual = (
        "https://www.ana.gov.br/sar/restportal/api/retornaMedicoes?"
        f"data={quote(data_str)}&siglaUf=&tipoSistema=3"
    )
    url_ana_anterior = (
        "https://www.ana.gov.br/sar/restportal/api/retornaMedicoes?"
        f"data={quote(data_str_anterior)}&siglaUf=&tipoSistema=3"
    )

    response_ana_atual = requests.get(url_ana_atual, headers=headers)

    if response_ana_atual.status_code == 200:
        dados_ana = response_ana_atual.json()
        dados_ana =pd.DataFrame(dados_ana)
        if "data" in dados_ana:
            df_dados_ana = dados_ana[dados_ana["estado"] == "Sistema Cantareira"].copy()
            df_dados_ana["data"] = pd.to_datetime(df_dados_ana["data"])
            df_dados_ana["data"] = df_dados_ana["data"].dt.strftime("%Y-%m-%d")

    response_ana_anterior = requests.get(url_ana_anterior, headers=headers)

    if response_ana_anterior.status_code == 200:
        dados_ana_anterior = response_ana_anterior.json()
        dados_ana_anterior =pd.DataFrame(dados_ana_anterior)
        if "data" in dados_ana_anterior:
            df_dados_ana_anterior = dados_ana_anterior[dados_ana_anterior["estado"] == "Sistema Cantareira"].copy()
            df_dados_ana_anterior["data"] = pd.to_datetime(df_dados_ana_anterior["data"])
            df_dados_ana_anterior["data"] = df_dados_ana_anterior["data"].dt.strftime("%Y-%m-%d")

    df_dados_ana["volumeUtil"] = pd.to_numeric(
        df_dados_ana["volumeUtil"],
        errors="coerce"
    )

    df_dados_ana_anterior["volumeUtil"] = pd.to_numeric(
        df_dados_ana_anterior["volumeUtil"],
        errors="coerce"
    )

    valor_volume = df_dados_ana["volumeUtil"].iloc[0]
    valor_volume_anterior = df_dados_ana_anterior["volumeUtil"].iloc[0]

    df_final_all_data_sabesp.loc[
        df_final_all_data_sabesp["Sistema"] == "Cantareira",
        "Volume Atual (%)"
    ] = valor_volume

    df_final_all_data_sabesp.loc[
        df_final_all_data_sabesp["Sistema"] == "Cantareira",
        "Volume Ano Anterior (%)"
    ] = valor_volume_anterior

    url_sim = f'https://cth.daee.sp.gov.br/ssdsp/api-private/TimeSeries/459/Data/{data_ano_anterior_str}/{data_atual_str}'
    response_sim = requests.get(url_sim, verify=False)

    if response_sim.status_code == 200:
        data = response_sim.json()

        if "dataCollection" in data:
            df_sim_atual = pd.DataFrame(data["dataCollection"])
            df_sim_atual_all = df_sim_atual.copy()
            df_sim_atual_all['Sistema'] = 'SIM'

            df_sim_atual_all["dateTime"] = pd.to_datetime(df_sim_atual_all["dateTime"])
            df_sim_atual_all["dateTime"] = df_sim_atual_all["dateTime"].dt.strftime("%Y-%m-%d")

            # valor do ano anterior
            filtro = df_sim_atual_all.loc[df_sim_atual_all['dateTime'] == data_ano_anterior_str, 'value']
            valor_ano_anterior = filtro.iloc[0] if not filtro.empty else None
            df_sim_atual_all["Volume Ano Anterior (%)"] = valor_ano_anterior

            # pega a linha do dia atual, senão última disponível
            if (df_sim_atual_all["dateTime"] == data_atual_str).any():
                linha_atual_sim = df_sim_atual_all.loc[df_sim_atual_all["dateTime"] == data_atual_str].sort_index().tail(1)
                linha_atual_sim["Data"] = data_atual_str
            else:
                linha_atual_sim = df_sim_atual_all.tail(1)
                linha_atual_sim["Data"] = linha_atual_sim["data"].tail(1).iloc[0] 

            # renomeia coluna
            linha_atual_sim = linha_atual_sim.rename(columns={"value": "Volume Atual (%)", "dateTime": "data"})      

    merged_data_sistemas = pd.concat([df_final_all_data_sabesp, linha_atual_sim], ignore_index=True)

    merged_data_sistemas['Diferença Vol. Anual (%)'] = merged_data_sistemas['Volume Atual (%)'] - merged_data_sistemas['Volume Ano Anterior (%)']

    merged_data_sistemas = merged_data_sistemas.rename(columns={'chuva_mm': 'Chuva (mm)', 'chuvaAcumuladaNoMes_mm': 'Acumulado no Mês (mm)', 'chuvaMediaHistorica_mm':'Média Histórica (mm)'})

    merged_data_sistemas = merged_data_sistemas[['Sistema', 'Volume Atual (%)', 'Volume Ano Anterior (%)', 'Diferença Vol. Anual (%)', 'Chuva (mm)', 'Acumulado no Mês (mm)', 'Média Histórica (mm)', 'Data']]

    cols = ['Chuva (mm)', 'Acumulado no Mês (mm)', 'Média Histórica (mm)']

    merged_data_sistemas[cols] = merged_data_sistemas[cols].replace(',', '.', regex=True)
    merged_data_sistemas[cols] = merged_data_sistemas[cols].apply(
        lambda col: pd.to_numeric(col, errors='coerce')
    )

    # Arredonda primeiro
    merged_data_sistemas[cols] = merged_data_sistemas[cols].round(1)

    # Formata cada elemento como string
    merged_data_sistemas[cols] = merged_data_sistemas[cols].applymap(lambda x: f'{x:.1f}' if pd.notna(x) else '-')
    
    # data_atual_str = data_value[:10]   # '2025-09-09'
    # merged_data_sistemas["Data"] = data_atual_str

    caminho_arquivo_json = os.path.join("results", f"sabesp_sistemas.json")
    merged_data_sistemas.to_json(caminho_arquivo_json, orient='records', force_ascii=False, indent=2)

def get_ssd_api(data_atual_str, data_7dias_str, data_14dias_str, data_21dias_str):
    dados_sistema = {
        "Cantareira": 0,
        "Alto Tietê": 1,
        "Guarapiranga": 2,
        "Cotia": 3,
        "Rio Grande": 4, 
        "Rio Claro":5,
        "São Lourenço": 17,
        "SIM": 459
    }


    #Chuva total no período
    chuva_sistemas_ssd = {
        "Cantareira": 369,
        "Alto Tietê": 345,
        "Guarapiranga":122,
        "Cotia": 381,
        "Rio Grande": 429, 
        "Rio Claro": 417,  
        "São Lourenço": 441,
        "SIM": 453  
    }   

    chuva_acumulada = {
        "Cantareira": 370,
        "Alto Tietê": 346,
        "Guarapiranga": 123,
        "Cotia": 382, 
        "Rio Grande": 430,
        "Rio Claro": 418,  
        "São Lourenço": 442,
        "SIM": 454
    }

    #"São Lourenço": 447,
    volume_sistema_ssd = {
        "Cantareira": 375,
        "Alto Tietê": 351,
        "Guarapiranga": 399,
        "Cotia": 387,
        "Rio Grande": 435, 
        "Rio Claro":423,
        "SIM": 459
    }

    df_sistemas_volume = pd.DataFrame(list(volume_sistema_ssd.items()), columns=["Sistema", "SistemaId"])

    all_volume =[]
    for _,data_volume in df_sistemas_volume.iterrows():
        id = data_volume["SistemaId"]

        url_volume = f'https://cth.daee.sp.gov.br/ssdsp/api-private/TimeSeries/{id}/Data/{data_21dias_str}/{data_atual_str}'
        response = requests.get(url_volume, verify=False)

        if response.status_code == 200:
            data = response.json()

            if "dataCollection" in data:
                df_atual = pd.DataFrame(data["dataCollection"])
                df_atual_all = df_atual.copy()
                df_atual_all['SistemaId'] = id

                # valor_atual = df_atual_all.loc[df_atual_all['dateTime'] == data_atual_str, 'value'].iloc[0]
                valor_atual = (
                    df_atual_all.loc[df_atual_all["dateTime"] <= data_atual_str, "value"]
                    .sort_index()
                    .iloc[-1]  # pega o último disponível
                )
                valor_7_dias = (df_atual_all.loc[df_atual_all['dateTime'] == data_7dias_str, 'value']
                    .reset_index(drop=True)
                    .get(0, None)  
                )
                valor_14_dias = (df_atual_all.loc[df_atual_all['dateTime'] == data_14dias_str, 'value']
                    .reset_index(drop=True)
                    .get(0, None)  
                )
                valor_21_dias = (df_atual_all.loc[df_atual_all['dateTime'] == data_21dias_str, 'value']
                    .reset_index(drop=True)
                    .get(0, None)  
                )

                stats = float(valor_atual)
                if stats >= 60:
                    cor = "#2e9619"  
                elif 40 <= stats < 60:
                    cor = '#f8d202'  
                elif 30 <= stats < 40:
                    cor = '#f95108' 
                elif 20 <= stats < 30:
                    cor = '#da070f'  
                elif stats < 20:
                    cor = '#8435b7' 

                df_atual_all["Volume atual (%)"] = valor_atual
                df_atual_all["Volume -7 dias (%)"] = valor_7_dias
                df_atual_all["Volume -14 dias (%)"] = valor_14_dias
                df_atual_all["Volume -21 dias (%)"] = valor_21_dias
                df_atual_all["cor_volume_atual"] = cor

                # df_atual_all = df_atual_all[df_atual_all['dateTime'] == data_atual_str]
                df_atual_all = df_atual_all.drop(columns={"deliveredAt", "value"})
                all_volume.append(df_atual_all)

    df_final = pd.concat(all_volume, ignore_index=True)
    merged_df_final= pd.merge(df_final, df_sistemas_volume, on='SistemaId', how='left')

    key = os.environ.get('KEY')
    value = os.environ.get('VALUE')
    headers = {key: value}
    url_sao_lourenco = f"https://ssdapi.sabesp.com.br/api/ssd/sistemas/sao-lourenco/dados/{data_21dias_str}/{data_atual_str}"
    response_sl = requests.get(url_sao_lourenco, headers=headers)

    if response_sl.status_code == 200:
        dados_sl = response_sl.json()
        if "data" in dados_sl:
            df_atual_sl = pd.DataFrame(dados_sl["data"])

            df_atual_sl['SistemaId'] = 447
            df_atual_sl['Sistema'] = "São Lourenço"

            df_atual_sl["data"] = pd.to_datetime(df_atual_sl["data"]).dt.date
            df_atual_sl["dateTime"] = pd.to_datetime(df_atual_sl["data"]).dt.strftime("%Y-%m-%d")
            
            if (df_atual_sl["data"] == data_atual_str).any():
                valor_atual = (
                    df_atual_sl.loc[df_atual_sl["data"] == data_atual_str, "volumeOperacional_porcentagem"]
                    .sort_index()
                    .iloc[-1]  # pega o último disponível
                )
            else: 
                valor_atual = df_atual_sl["volumeOperacional_porcentagem"].iloc[-1]

            valor_7_dias = (df_atual_sl.loc[df_atual_sl['dateTime'] == data_7dias_str, 'volumeOperacional_porcentagem']
                .reset_index(drop=True)
                .get(0, None)  
            )
            valor_14_dias = (df_atual_sl.loc[df_atual_sl['dateTime'] == data_14dias_str, 'volumeOperacional_porcentagem']
                .reset_index(drop=True)
                .get(0, None)  
            )
            valor_21_dias = (df_atual_sl.loc[df_atual_sl['dateTime'] == data_21dias_str, 'volumeOperacional_porcentagem']
                .reset_index(drop=True)
                .get(0, None)  
            )

            stats = float(valor_atual)
            if stats >= 60:
                cor = "#2e9619"  
            elif 40 <= stats < 60:
                cor = '#f8d202'  
            elif 30 <= stats < 40:
                cor = '#f95108' 
            elif 20 <= stats < 30:
                cor = '#da070f'  
            elif stats < 20:
                cor = '#8435b7' 

            df_atual_sl["Volume atual (%)"] = valor_atual
            df_atual_sl["Volume -7 dias (%)"] = valor_7_dias
            df_atual_sl["Volume -14 dias (%)"] = valor_14_dias
            df_atual_sl["Volume -21 dias (%)"] = valor_21_dias
            df_atual_sl["cor_volume_atual"] = cor

    merged_df_final = pd.concat([merged_df_final, df_atual_sl], ignore_index=True)

    return merged_df_final

def get_ssd_api_comparacao(data_ano_anterior_str):

    #"São Lourenço": 447,
    volume_sistema_ssd = {
        "Cantareira": 375,
        "Alto Tietê": 351,
        "Guarapiranga": 399,
        "Cotia": 387,
        "Rio Grande": 435, 
        "Rio Claro":423,
        "SIM": 459
    }

    df_sistemas_volume = pd.DataFrame(list(volume_sistema_ssd.items()), columns=["Sistema", "SistemaId"])
    data_inicial = "2000-01-01"
    all_volume =[]
    for _,data_volume in df_sistemas_volume.iterrows():
        id = data_volume["SistemaId"]

        url_volume = f'https://cth.daee.sp.gov.br/ssdsp/api-private/TimeSeries/{id}/Data/{data_inicial}/{data_ano_anterior_str}'

        response = requests.get(url_volume, verify=False)

        if response.status_code == 200:
            data = response.json()

            if "dataCollection" in data and len(data["dataCollection"]) > 0:
                df_atual = pd.DataFrame(data["dataCollection"])
                df_atual_all = df_atual.copy()
                df_atual_all['SistemaId'] = id
                
                # valor_ano_anterior = df_atual_all.loc[df_atual_all['dateTime'] == data_ano_anterior_str, 'value'].iloc[0]

                # df_atual_all["Volume Ano Anterior (%)"] = valor_ano_anterior

                # df_atual_all = df_atual_all[df_atual_all['dateTime'] == data_ano_anterior_str]

                df_atual_all.rename(columns={"value": "Volume Ano Anterior (%)"}, inplace=True)

                df_atual_all = df_atual_all.drop(columns={"deliveredAt"})
                all_volume.append(df_atual_all)

            else:
                df_atual_all = pd.DataFrame()
                df_atual_all['SistemaId'] = id
                df_atual_all["Volume Ano Anterior (%)"] = None
                all_volume.append(df_atual_all)


    df_final = pd.concat(all_volume, ignore_index=True)

    key = os.environ.get('KEY')
    value = os.environ.get('VALUE')
    headers = {key: value}


    hoje = datetime.today()
    dia_mes = hoje.strftime("%m-%d")  # apenas mês e dia
    anos = range(2019, 2025)  # 2020 a 2024

    all_data = []
    data_inicial_sl = '2019-01-01'

    for ano in anos:
        data_str = f"{ano}-{dia_mes}"  # cria "2020-10-26", "2021-10-26", etc.
        url = f"https://ssdapi.sabesp.com.br/api/ssd/sistemas/sao-lourenco/dados/{data_str}/{data_str}"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            dados = response.json()
            if "data" in dados and len(dados["data"]) > 0:
                df = pd.DataFrame(dados["data"])
                df = df[["data", "volumeOperacional_porcentagem"]]
                df['SistemaId'] = 447
                df["dateTime"] = pd.to_datetime(df["data"]).dt.strftime("%Y-%m-%d")
                df.rename(columns={"volumeOperacional_porcentagem": "Volume Ano Anterior (%)"}, inplace=True)
                df = df.drop(columns=["data"])
                all_data.append(df)
            else:
                # caso não tenha dado nenhum valor nesse ano, adiciona linha vazia
                all_data.append(pd.DataFrame({
                    "SistemaId": [447],
                    "dateTime": [data_str],
                    "Volume Ano Anterior (%)": [None]
                }))

    df_atual_sl = pd.concat(all_data, ignore_index=True)

    merged_df_final = pd.concat([df_final, df_atual_sl], ignore_index=True)
    return merged_df_final


def get_ssd_vazao_natural(data_atual_str):

    vazao_natural = {
        "Cantareira": 855, 
        "SIM": 939,
        "Alto Tietê": 831,
        "Guarapiranga": 879,
        "Cotia": 867,
        "Rio Grande":915,
        "Rio Claro":903,
        "São Lourenço":927
    }

    df_sistemas_vazao = pd.DataFrame(list(vazao_natural.items()), columns=["Sistema", "SistemaId"]).copy()

    data_base = '1953-01-01'

    all_volume =[]
    for _,data_volume in df_sistemas_vazao.iterrows():
        id = data_volume["SistemaId"]

        url_volume = f'https://cth.daee.sp.gov.br/ssdsp/api-private/TimeSeries/{id}/Data/{data_base}/{data_atual_str}'
        response = requests.get(url_volume, verify=False)

        if response.status_code == 200:
            data = response.json()

            if "dataCollection" in data:
                df_atual = pd.DataFrame(data["dataCollection"])
                df_atual_all = df_atual.copy()
                df_atual_all['SistemaId'] = id

                df_atual_all["dateTime"] = pd.to_datetime(df_atual_all["dateTime"])

                # criar coluna só com mês e dia (formato "01-01")
                df_atual_all["mes_dia"] = df_atual_all["dateTime"].dt.strftime("%m-%d")

                df_atual_all["ano"] = df_atual_all["dateTime"].dt.strftime("%Y")

                # df_grouped = df_atual_all.groupby("mes_ano")["Volume"].sum().reset_index()
                df_grouped = df_atual_all.groupby(['mes_dia', 'SistemaId'], as_index=False).agg(
                    min_value=('value', 'min'),
                    mean_value=('value', 'mean')
                )

                df_atual_all = pd.merge(df_atual_all, df_grouped, on=['mes_dia', 'SistemaId'], how='left')
                all_volume.append(df_atual_all)


    df_final = pd.concat(all_volume, ignore_index=True)
    df_final = pd.merge(df_final, df_sistemas_vazao, on='SistemaId', how='left')
    df_final_historico_mensal = df_final[['mes_dia', 'min_value', 'mean_value', 'Sistema']]
    df_final_historico_mensal = (
        df_final_historico_mensal
        .groupby(['mes_dia', 'Sistema'], as_index=False)
        .agg({
            'min_value': 'mean',
            'mean_value': 'mean'
        })
    )

    vazao_natural_diaria = {
        "Cantareira":373,
        "Alto Tietê": 349,
        "Guarapiranga": 397,
        "Cotia": 385,
        "Rio Grande":433,
        "Rio Claro":421,
        "São Lourenço":445,
        "SIM": 457
    }

    df_vazao_natural_diaria = pd.DataFrame(list(vazao_natural_diaria.items()), columns=["Sistema", "SistemaId"]).copy()

    data_base = '1953-01-01'

    vazao_natural_diaria_all =[]
    for _,data_volume in df_vazao_natural_diaria.iterrows():
        id = data_volume["SistemaId"]

        url_volume = f'https://cth.daee.sp.gov.br/ssdsp/api-private/TimeSeries/{id}/Data/{data_base}/{data_atual_str}'
        response = requests.get(url_volume, verify=False)

        if response.status_code == 200:
            data = response.json()

            if "dataCollection" in data:
                df_atual = pd.DataFrame(data["dataCollection"])
                df_atual_all = df_atual.copy()
                df_atual_all['SistemaId'] = id

                df_atual_all["dateTime"] = pd.to_datetime(df_atual_all["dateTime"])

                # criar coluna só com mês e dia (formato "01-01")
                df_atual_all["mes_dia"] = df_atual_all["dateTime"].dt.strftime("%m-%d")

                df_atual_all["ano"] = df_atual_all["dateTime"].dt.strftime("%Y")

                df_atual_all["mes_ano"] = df_atual_all["dateTime"].dt.strftime("%Y-%m")

                df_atual_all["data_mes"] = pd.to_datetime(df_atual_all["mes_ano"] + "-01")

                # df_grouped = df_atual_all.groupby("mes_ano")["Volume"].sum().reset_index()
                df_grouped = df_atual_all.groupby(['mes_dia', 'SistemaId'], as_index=False).agg(
                    min_value=('value', 'min'),
                    mean_value=('value', 'mean')
                )

                df_atual_all = pd.merge(df_atual_all, df_grouped, on=['mes_dia', 'SistemaId'], how='left')
                vazao_natural_diaria_all.append(df_atual_all)

    df_vazao_natural_diaria_all = pd.concat(vazao_natural_diaria_all, ignore_index=True)
    df_vazao_natural_diaria_all = pd.merge(df_vazao_natural_diaria_all, df_vazao_natural_diaria, on='SistemaId', how='left')    
    df_vazao_natural_mensal_all = df_vazao_natural_diaria_all.groupby(['data_mes', 'SistemaId', 'Sistema', 'ano'], as_index=False).agg(
                    value=('value', 'mean')
                )
    df_vazao_natural_mensal_all["mes_dia"]=df_vazao_natural_mensal_all['data_mes'].dt.strftime("%m-%d")


    df_vazao_natural_mensal = df_vazao_natural_mensal_all.copy()
    df_vazao_natural_mensal = df_vazao_natural_mensal.groupby(['mes_dia', 'SistemaId'], as_index=False).agg(
                    min_value=('value', 'min'),
                    mean_value=('value', 'mean')
                )
    
    # df_vazao_natural_mensal_all = pd.merge(df_vazao_natural_mensal_all, df_vazao_natural_mensal, on=['mes_dia', 'SistemaId'], how='left')
    df_vazao_natural_mensal_all = pd.merge(df_vazao_natural_mensal_all, df_final_historico_mensal, on=['mes_dia','Sistema'], how='left')
    df_vazao_natural_mensal_all = df_vazao_natural_mensal_all.rename(columns={"data_mes": "dateTime"})
    # df_vazao_natural_mensal_all = df_vazao_natural_mensal_all.sort_values(['dateTime', 'SistemaId'])
    print("df_vazao_natural_mensal_all")
    print(df_vazao_natural_mensal_all)

    return df_vazao_natural_mensal_all, df_vazao_natural_diaria_all

def get_ssd_vazao_captada(data_atual_str):

    vazao_captada_mensal = {
        "Cantareira": 861, 
        "SIM": 945,
        "Alto Tietê": 837,
        "Guarapiranga": 885,
        "Cotia": 873,
        "Rio Grande":921,
        "Rio Claro":909,
        "São Lourenço":933
    }



    df_sistemas_vazao = pd.DataFrame(list(vazao_captada_mensal.items()), columns=["Sistema", "SistemaId"]).copy()

    data_base = '1953-01-01'

    all_volume =[]
    for _,data_volume in df_sistemas_vazao.iterrows():
        id = data_volume["SistemaId"]

        url_volume = f'https://cth.daee.sp.gov.br/ssdsp/api-private/TimeSeries/{id}/Data/{data_base}/{data_atual_str}'
        response = requests.get(url_volume, verify=False)

        if response.status_code == 200:
            data = response.json()

            if "dataCollection" in data:
                df_atual = pd.DataFrame(data["dataCollection"])
                df_atual_all = df_atual.copy()
                df_atual_all['SistemaId'] = id

                df_atual_all["dateTime"] = pd.to_datetime(df_atual_all["dateTime"])

                # criar coluna só com mês e dia (formato "01-01")
                df_atual_all["mes_dia"] = df_atual_all["dateTime"].dt.strftime("%m-%d")

                df_atual_all["ano"] = df_atual_all["dateTime"].dt.strftime("%Y")

                # df_grouped = df_atual_all.groupby("mes_ano")["Volume"].sum().reset_index()
                df_grouped = df_atual_all.groupby(['mes_dia', 'SistemaId'], as_index=False).agg(
                    min_value=('value', 'min'),
                    mean_value=('value', 'mean')
                )

                df_atual_all = pd.merge(df_atual_all, df_grouped, on=['mes_dia', 'SistemaId'], how='left')
                all_volume.append(df_atual_all)


    df_final = pd.concat(all_volume, ignore_index=True)
    df_final = pd.merge(df_final, df_sistemas_vazao, on='SistemaId', how='left')


    vazao_captada_diaria = {
        "Cantareira":379,
        "SIM":463,
        "Alto Tietê": 355,
        "Guarapiranga": 403,
        "Cotia": 391,
        "Rio Grande":439,
        "Rio Claro":427,
        "São Lourenço":451

    }

    df_vazao_captada_diaria = pd.DataFrame(list(vazao_captada_diaria.items()), columns=["Sistema", "SistemaId"]).copy()

    data_base = '1953-01-01'

    vazao_captada_diaria_all =[]
    for _,data_volume in df_vazao_captada_diaria.iterrows():
        id = data_volume["SistemaId"]

        url_volume = f'https://cth.daee.sp.gov.br/ssdsp/api-private/TimeSeries/{id}/Data/{data_base}/{data_atual_str}'
        response = requests.get(url_volume, verify=False)

        if response.status_code == 200:
            data = response.json()

            if "dataCollection" in data:
                df_atual = pd.DataFrame(data["dataCollection"])
                df_atual_all = df_atual.copy()
                df_atual_all['SistemaId'] = id

                df_atual_all["dateTime"] = pd.to_datetime(df_atual_all["dateTime"])

                # criar coluna só com mês e dia (formato "01-01")
                df_atual_all["mes_dia"] = df_atual_all["dateTime"].dt.strftime("%m-%d")

                df_atual_all["ano"] = df_atual_all["dateTime"].dt.strftime("%Y")

                # df_grouped = df_atual_all.groupby("mes_ano")["Volume"].sum().reset_index()
                df_grouped = df_atual_all.groupby(['mes_dia', 'SistemaId'], as_index=False).agg(
                    min_value=('value', 'min'),
                    mean_value=('value', 'mean')
                )

                df_atual_all = pd.merge(df_atual_all, df_grouped, on=['mes_dia', 'SistemaId'], how='left')
                vazao_captada_diaria_all.append(df_atual_all)

    df_vazao_captada_diaria_all = pd.concat(vazao_captada_diaria_all, ignore_index=True)
    df_vazao_captada_diaria_all = pd.merge(df_vazao_captada_diaria_all, df_vazao_captada_diaria, on='SistemaId', how='left')            


    return df_final, df_vazao_captada_diaria_all

def get_ssd_vazao_afluente(data_atual_str):

    vazao_afluente_diaria = {
        "SIM":455,
        "Cantareira": 371,
        "Alto Tietê": 347,
        "Guarapiranga": 395,
        "Cotia": 383,
        "Rio Grande":431,
        "Rio Claro":419,
        "São Lourenço":443
    }

    df_vazao_afluente_diaria = pd.DataFrame(list(vazao_afluente_diaria.items()), columns=["Sistema", "SistemaId"]).copy()

    data_base = '1953-01-01'

    vazao_afluente_diaria_all =[]
    for _,data_volume in df_vazao_afluente_diaria.iterrows():
        id = data_volume["SistemaId"]

        url_volume = f'https://cth.daee.sp.gov.br/ssdsp/api-private/TimeSeries/{id}/Data/{data_base}/{data_atual_str}'
        response = requests.get(url_volume, verify=False)

        if response.status_code == 200:
            data = response.json()

            if "dataCollection" in data:
                df_atual = pd.DataFrame(data["dataCollection"])
                df_atual_all = df_atual.copy()
                df_atual_all['SistemaId'] = id

                vazao_afluente_diaria_all.append(df_atual_all)

    df_vazao_afluente_diaria_all = pd.concat(vazao_afluente_diaria_all, ignore_index=True)
    df_vazao_afluente_diaria_all = pd.merge(df_vazao_afluente_diaria_all, df_vazao_afluente_diaria, on='SistemaId', how='left')            


    return df_vazao_afluente_diaria_all

def get_ssd_descarregada(data_atual_str):

    vazao_descarregada_diaria = {
        "Cantareira":372, 
        "Atibainha":48,
        "Jaguari / Jacareí": 136,
        "Paiva Castro":158, 
        "Cachoeira":81
    }

    mes = {
        "Janeiro": 1,
        "Fevereiro": 2,
        "Março": 3,
        "Abril": 4,
        "Maio": 5,
        "Junho": 6,
        "Julho": 7,
        "Agosto": 8,
        "Setembro": 9,
        "Outubro": 10,
        "Novembro": 11,
        "Dezembro":12
    }

    df_vazao_afluente_diaria = pd.DataFrame(list(vazao_descarregada_diaria.items()), columns=["Sistema", "SistemaId"]).copy()
    df_meses = pd.DataFrame(list(mes.items()), columns=["Mês", "mes_n"]).copy()


    data_base = '1953-01-01'

    vazao_descarregada_diaria_all =[]
    for _,data_volume in df_vazao_afluente_diaria.iterrows():
        id = data_volume["SistemaId"]

        url_volume = f'https://cth.daee.sp.gov.br/ssdsp/api-private/TimeSeries/{id}/Data/{data_base}/{data_atual_str}'
        response = requests.get(url_volume, verify=False)

        if response.status_code == 200:
            data = response.json()

            if "dataCollection" in data:
                df_atual = pd.DataFrame(data["dataCollection"])
                df_atual_all = df_atual.copy()
                df_atual_all['SistemaId'] = id

                df_atual_all["dateTime"] = pd.to_datetime(df_atual_all["dateTime"])
                df_atual_all["mes_n"] = df_atual_all["dateTime"].dt.strftime("%m")
                df_atual_all["mes_n"] =  df_atual_all["mes_n"].astype(int)

                vazao_descarregada_diaria_all.append(df_atual_all)

    df_vazao_descarregada_diaria_all = pd.concat(vazao_descarregada_diaria_all, ignore_index=True)
    df_vazao_descarregada_diaria_all = pd.merge(df_vazao_descarregada_diaria_all, df_vazao_afluente_diaria, on='SistemaId', how='left')
    df_vazao_descarregada_diaria_all = pd.merge(df_vazao_descarregada_diaria_all, df_meses, on='mes_n', how='left')            
    print(df_vazao_descarregada_diaria_all)

    return df_vazao_descarregada_diaria_all

def get_ssd_transferencias(data_atual_str):

    transferencia = {
        "UHE Jaguari - Atibainha": 813, 
        "EEAB Santa Inês": 809, 
        "Túnel 7":816,
        "Túnel 6":815,
        "Túnel 5":815,
    }

    mes = {
        "Janeiro": 1,
        "Fevereiro": 2,
        "Março": 3,
        "Abril": 4,
        "Maio": 5,
        "Junho": 6,
        "Julho": 7,
        "Agosto": 8,
        "Setembro": 9,
        "Outubro": 10,
        "Novembro": 11,
        "Dezembro":12
    }

    df_sistemas_transferencia = pd.DataFrame(list(transferencia.items()), columns=["Sistema", "SistemaId"]).copy()
    df_meses = pd.DataFrame(list(mes.items()), columns=["Mês", "mes_n"]).copy()

    data_base = '2025-01-01'

    all_volume =[]
    for _,data_volume in df_sistemas_transferencia.iterrows():
        id = data_volume["SistemaId"]

        url_volume = f'https://cth.daee.sp.gov.br/ssdsp/api-private/TimeSeries/{id}/Data/{data_base}/{data_atual_str}'
        response = requests.get(url_volume, verify=False)

        if response.status_code == 200:
            data = response.json()

            if "dataCollection" in data:
                df_atual = pd.DataFrame(data["dataCollection"])
                df_atual_all = df_atual.copy()
                df_atual_all['SistemaId'] = id

                df_atual_all["dateTime"] = pd.to_datetime(df_atual_all["dateTime"])

                df_atual_all["mes_n"] = df_atual_all["dateTime"].dt.strftime("%m")
                df_atual_all["mes_n"] =  df_atual_all["mes_n"].astype(int)

                df_atual_all["ano"] = df_atual_all["dateTime"].dt.strftime("%Y")

                all_volume.append(df_atual_all)

            
    df_final = pd.concat(all_volume, ignore_index=True)

    df_final = pd.merge(df_final, df_sistemas_transferencia, on='SistemaId', how='left')
    df_final = pd.merge(df_final, df_meses, on='mes_n', how='left')

    transferencia_dia = {
        "UHE Jaguari - Atibainha": 331,
        "EEAB Santa Inês": 327,
        "Túnel 5": 332,
        "Túnel 6": 333,
        "Túnel 7":334,
        "EEAB Biritiba": 335,
        "Biritiba - Jundiaí": 337,
        "Jundiaí - Taiçupeba": 330,
        "Biritiba - Dique": 329
    }

    df_sistemas_transferencia_dia = pd.DataFrame(list(transferencia_dia.items()), columns=["Sistema", "SistemaId"]).copy()

    hoje = datetime.today()
    primeiro_dia = hoje.replace(day=1)

    all_transferencia =[]
    for _,data_volume in df_sistemas_transferencia_dia.iterrows():
        id = data_volume["SistemaId"]

        url_transferencia_dia = f'https://cth.daee.sp.gov.br/ssdsp/api-private/TimeSeries/{id}/Data/{primeiro_dia}/{data_atual_str}'
        response = requests.get(url_transferencia_dia, verify=False)

        if response.status_code == 200:
            data = response.json()

            if "dataCollection" in data:
                df_atual = pd.DataFrame(data["dataCollection"])
                df_transferencia = df_atual.copy()
                df_transferencia['SistemaId'] = id

                df_transferencia["dateTime"] = pd.to_datetime(df_transferencia["dateTime"])

                df_transferencia["mes_dia"] = df_transferencia["dateTime"].dt.strftime("%d-%m")

                df_transferencia["ano"] = df_transferencia["dateTime"].dt.strftime("%Y")

                all_transferencia.append(df_transferencia)

    all_transferencia_final = pd.concat(all_transferencia, ignore_index=True)

    all_transferencia_final = pd.merge(all_transferencia_final, df_sistemas_transferencia_dia, on='SistemaId', how='left')

    return df_final, all_transferencia_final

def calculate_media_movel_captda(df_sim_atual_all, vazao_captada_diaria, vazao_afluente, vazao_descarregada, sistema_selecionado):
    df_sim_atual_all = df_sim_atual_all[df_sim_atual_all['Sistema']==sistema_selecionado]
    vazao_captada_diaria = vazao_captada_diaria[vazao_captada_diaria["Sistema"] == sistema_selecionado]
    vazao_afluente = vazao_afluente[vazao_afluente["Sistema"] == sistema_selecionado]

    df_sim_atual_all.rename(columns={"value": "Volume"}, inplace=True)
    vazao_captada_diaria.rename(columns={"value": "Vazão Captada"}, inplace=True)
    vazao_afluente.rename(columns={"value": f"Vazão Afluente {sistema_selecionado}"}, inplace=True)
    vazao_descarregada.rename(columns={"value": "Vazão descarregada Cantareira"}, inplace=True)

    df_sim_atual_all["dateTime"] = pd.to_datetime(df_sim_atual_all["dateTime"]).dt.strftime("%Y-%m-%d")
    vazao_captada_diaria["dateTime"] = pd.to_datetime(vazao_captada_diaria["dateTime"]).dt.strftime("%Y-%m-%d")
    vazao_afluente["dateTime"] = pd.to_datetime(vazao_afluente["dateTime"]).dt.strftime("%Y-%m-%d")
    vazao_descarregada["dateTime"] = pd.to_datetime(vazao_descarregada["dateTime"]).dt.strftime("%Y-%m-%d")

    df_sim_atual_all = pd.merge(df_sim_atual_all, vazao_captada_diaria[["dateTime", "Vazão Captada"]], on="dateTime", how="left")
    df_sim_atual_all = pd.merge(df_sim_atual_all, vazao_afluente[["dateTime", f"Vazão Afluente {sistema_selecionado}"]], on="dateTime", how="left")
    df_sim_atual_all = pd.merge(df_sim_atual_all, vazao_descarregada[["dateTime", "Vazão descarregada Cantareira"]], on="dateTime", how="left") 

    df_sim_atual_all["dateTime"] = pd.to_datetime(df_sim_atual_all["dateTime"], errors="coerce")
    df_sim_atual_all = df_sim_atual_all.sort_values(by='dateTime').reset_index(drop=True)

    x = 14  # Média móvel de 7 dias
    colunas_mm = ['Vazão Captada', f'Vazão Afluente {sistema_selecionado}'] #colunas_mm = ['Vazão Captada', 'Vazão Afluente SIM', 'Vazão descarregada Cantareira']
    for col in colunas_mm:
        df_sim_atual_all[f'MediaMovel_{col}_{x}d'] = df_sim_atual_all[col].rolling(window=x, min_periods=1).mean()

    df_sim_atual_all[f'TaxaVar_{x}d'] = (df_sim_atual_all['Volume'] - df_sim_atual_all['Volume'].shift(x)) / x

    return df_sim_atual_all

def get_telemetric_stations(data_atual_str):

    agora = datetime.now()
    end_date = (agora + timedelta(days=1))
    end_date_str = end_date.strftime("%Y-%m-%d")
    #ajustar a lógica da data par pegar o end_date como data atual + 1 até às 03:00 da manhã

    stations_id = [29592, 30846, 29591]
    all_stations =[]
    for id in stations_id:

        url = f"https://cth.daee.sp.gov.br/sibh/api/v2/measurements?end_date={end_date_str}T23:59:59.999Z&group_type=minute&start_date={data_atual_str}T00:00:00.000Z&station_prefix_ids[]={id}"    
        response = requests.get(url, verify=False)

        if response.status_code == 200:
            data = response.json()

            if "measurements" in data:
                df_atual = pd.DataFrame(data["measurements"])
                df_atual["date"] = pd.to_datetime(df_atual["date"])
                df_atual = df_atual.sort_values("date")
                ultimo_registro = df_atual.tail(1)
                all_stations.append(ultimo_registro)

    all_stations_data = pd.concat(all_stations, ignore_index=True)
    geometry = [Point(xy) for xy in zip(all_stations_data["longitude"], all_stations_data["latitude"])]

    # Transformar em GeoDataFrame
    gdf_all_stations_data = gpd.GeoDataFrame(all_stations_data, geometry=geometry, crs="EPSG:4326")
    gdf_all_stations_data["date"] = gdf_all_stations_data["date"].dt.strftime("%Y/%m/%d %H:%M")

    return gdf_all_stations_data


@st.cache_data(ttl=3600, show_spinner="Carregando dados...")
def load_dados(data_atual_str, data_ano_anterior_str, data_7dias_str, data_14dias_str, data_21dias_str):
    vazao_natural, vazao_natural_diaria = get_ssd_vazao_natural(data_atual_str)
    vazao_captada, vazao_captada_diaria = get_ssd_vazao_captada(data_atual_str)
    vazao_afluente = get_ssd_vazao_afluente(data_atual_str)
    vazao_descarregada = get_ssd_descarregada(data_atual_str)
    transferencias_all, all_transferencia_final = get_ssd_transferencias(data_atual_str)
    sistemas_ano_comparacao = get_ssd_api_comparacao(data_ano_anterior_str)
    merged_data_sistemas_all = get_ssd_api(data_atual_str, data_7dias_str, data_14dias_str, data_21dias_str)

    volume_sistema_ssd = {
            "Cantareira": 375,
            "Alto Tietê": 351,
            "Guarapiranga": 399,
            "Cotia": 387,
            "Rio Grande": 435, 
            "Rio Claro":423,
            "SIM": 459
        }

    df_sistemas_volume = pd.DataFrame(list(volume_sistema_ssd.items()), columns=["Sistema", "SistemaId"])
    data_inicial = '2025-06-01' 
    all_volume =[]
    for _,data_volume in df_sistemas_volume.iterrows():
        id = data_volume["SistemaId"]

        url_volume = f'https://cth.daee.sp.gov.br/ssdsp/api-private/TimeSeries/{id}/Data/{data_inicial}/{data_atual_str}'
        response = requests.get(url_volume, verify=False)

        if response.status_code == 200:
            data = response.json()

            if "dataCollection" in data:
                df_sim_atual = pd.DataFrame(data["dataCollection"])
                df_sim_atual_all = df_sim_atual.copy()
                df_sim_atual_all['SistemaId'] = id

                all_volume.append(df_sim_atual_all)

    df_final_all = pd.concat(all_volume, ignore_index=True)
    df_final_all_volume= pd.merge(df_final_all, df_sistemas_volume, on='SistemaId', how='left')
    
    key = os.environ.get('KEY')
    value = os.environ.get('VALUE')
    headers = {key: value}
    url_sao_lourenco = f"https://ssdapi.sabesp.com.br/api/ssd/sistemas/sao-lourenco/dados/{data_inicial}/{data_atual_str}"
    response_sl = requests.get(url_sao_lourenco, headers=headers)

    if response_sl.status_code == 200:
        dados_sl = response_sl.json()
        if "data" in dados_sl:
            df_atual_sl = pd.DataFrame(dados_sl["data"])
            df_atual_sl = df_atual_sl[["data", 'volumeOperacional_porcentagem']]
            df_atual_sl['SistemaId'] = 447
            df_atual_sl['Sistema'] = "São Lourenço"
            df_atual_sl["data"] = pd.to_datetime(df_atual_sl["data"])
            df_atual_sl["data"] = df_atual_sl["data"].dt.strftime("%Y-%m-%d")
            
            df_atual_sl = df_atual_sl.rename(columns={"volumeOperacional_porcentagem": "value", "data": "dateTime"})

    df_final_all_volume = pd.concat([df_final_all_volume, df_atual_sl], ignore_index=True)

    data_dia_anterior = datetime.today() - timedelta(days=1)
    data_dia_anterior_str = data_dia_anterior.strftime('%Y-%m-%d')

    if data_atual_str in merged_data_sistemas_all['dateTime'].values:
        merged_data_sistemas = merged_data_sistemas_all[
            merged_data_sistemas_all['dateTime'] == data_atual_str
        ]
    elif data_dia_anterior_str in merged_data_sistemas_all['dateTime'].values:
        merged_data_sistemas = merged_data_sistemas_all[
            merged_data_sistemas_all['dateTime'] == data_dia_anterior_str
        ]

    gdflimite = gpd.read_file("data/limiteestadualsp.shp")
       

    gdfsistemas = gpd.read_file("data/bacia_sistemas_uniao.shp", encoding="utf-8")
    gdfsistemas = gdfsistemas.set_crs("EPSG:4326")
    gdfsistemas['Sistema'] = gdfsistemas['Sistema'].replace('Sao Lourenço', 'São Lourenço')


    gdf_pariba_do_sul = gpd.read_file("data/paraiba_do_sul.shp")
    gdf_hidrografia = gpd.read_file("data/HIDROGRAFIA_ESP_ANA_2013_LN.shp")
    gdf_vazao_natural = gpd.read_file("data/vazao_natural.shp")
    gdf_vazao_captada= gpd.read_file("data/vazao_captada.shp")

    stations_monitoramento = get_telemetric_stations(data_atual_str)

    gdf_transposicao = gpd.read_file("data/dados_sistemas.shp")

    gdf_reservatorios = gpd.read_file("data/reservatorios_sabesp_sistemas.shp")

    return (merged_data_sistemas, df_final_all_volume, vazao_natural, vazao_natural_diaria, vazao_captada, vazao_captada_diaria,
            vazao_afluente, vazao_descarregada, transferencias_all, all_transferencia_final, sistemas_ano_comparacao, 
            gdflimite, gdfsistemas, gdf_pariba_do_sul, gdf_hidrografia,gdf_vazao_natural,gdf_vazao_captada,stations_monitoramento, gdf_transposicao, gdf_reservatorios)

def creat_dashboard(lista_anos_str, data_atual_str, data_ano_anterior_str, dia, mes, ano_usado, data_7dias_str, data_14dias_str, data_21dias_str):
    colun1, colun2, colun3= st.columns([0.2, 2.0, 0.2])

    map1, map2 = st.columns([3.0, 1.5])    

    with colun2:
        
        (merged_data_sistemas, df_sim_atual_all, vazao_natural, vazao_natural_diaria,
        vazao_captada, vazao_captada_diaria,
        vazao_afluente, vazao_descarregada,
        transferencias_all, all_transferencia_final, sistemas_ano_comparacao_full,
        gdflimite, gdfsistemas, gdf_pariba_do_sul, gdf_hidrografia,gdf_vazao_natural,gdf_vazao_captada,
        stations_monitoramento,gdf_transposicao,gdf_reservatorios) = load_dados(data_atual_str, data_ano_anterior_str, data_7dias_str, data_14dias_str, data_21dias_str)

        sistemas_list = vazao_natural['Sistema'].unique().tolist()
        
        tunel_list = transferencias_all['Sistema'].unique().tolist()

        if "sistema_filter" not in st.session_state:
            st.session_state.sistema_filter = "SIM"

        if "tunel_transferencia" not in st.session_state:
            st.session_state.tunel_transferencia = "UHE Jaguari - Atibainha"
        
        con1, con2, con3, con4, con5 = st.columns([1.0, 1.5, 1.5, 1.5, 1.0])
        with con2:
            ano_selecionado = st.selectbox(
                "Selecione novo ano para compação ",
                options=lista_anos_str,
                index=lista_anos_str.index(st.session_state.data_filter),
                label_visibility="visible"
            )

            if ano_selecionado != st.session_state.data_filter:
                st.session_state.data_filter = ano_selecionado
                data_ano_anterior_str = f"{ano_selecionado}-{mes:02d}-{dia:02d}"


        with con3:
            st.session_state.sistema_filter = st.selectbox(
                "Selecione sistema",
                options=sistemas_list,
                index=sistemas_list.index(st.session_state.sistema_filter),
                label_visibility="visible"
            )

        
        with con4:
            st.session_state.tunel_transferencia = st.selectbox(
                "Selecione Túnel",
                options=tunel_list,
                index=tunel_list.index(st.session_state.tunel_transferencia),
                label_visibility="visible"
            )
            

        sistema_selecionado = st.session_state.sistema_filter
        tunel_selecionado = st.session_state.tunel_transferencia
        ano_selecionado = st.session_state.data_filter
        
        ano_filtro = f"{ano_selecionado}-{mes:02d}-{dia:02d}"

        st.write(f"""
            <div style="color: black; display: flex; justify-content: center; align-items: center; padding: 20px;">
                <p style="font-size: 16px; text-align: center;">
                    Comparação entre volume(%) atual e o volume em {dia:02d}/{mes:02d}/{ano_selecionado}
                </p>
            </div>
        """, unsafe_allow_html=True)

        sistemas_ano_comparacao = sistemas_ano_comparacao_full[
            sistemas_ano_comparacao_full["dateTime"] == ano_filtro
        ].copy()

        merged_data_sistemas = pd.merge(merged_data_sistemas, sistemas_ano_comparacao, on='SistemaId', how='left' ).copy()

        merged_data_sistemas = merged_data_sistemas.rename(columns={"dateTime_x": "dateTime"})
        merged_data_sistemas["dateTime"] = pd.to_datetime(merged_data_sistemas["dateTime"])
        merged_data_sistemas["dateTime"] = merged_data_sistemas["dateTime"].dt.strftime("%Y-%m-%d")
        merged_data_sistemas = merged_data_sistemas.drop(columns=['dateTime_y', 'data'])

        merged_data_sistemas['diferença'] = merged_data_sistemas['Volume atual (%)'] - merged_data_sistemas['Volume Ano Anterior (%)']
        merged_data_sistemas['simbolo'] = merged_data_sistemas['diferença'].apply(lambda x: '🠗' if x < 0 else '🠕')
        merged_data_sistemas['cor_diferença'] = merged_data_sistemas['diferença'].apply(lambda x: "#660000" if x < 0 else "#2F582B")

        legenda ={
                "E0 - Normal": '#268b12',
                "E1 - Atenção": '#f8d202',
                "E2 - Alerta":'#f95108',
                "E3 - Crítico":'#da070f',
                "E4 - Emergência":'#8435b7'
            }
        
        regra_operacao_vazao_cantareira = {
            "Faixa 1": "Normal - 33,0",
            "Faixa 2": "Atenção - 31,0",
            "Faixa 3": "Alerta - 27,0",
            "Faixa 4": "Restrição - 23,0 + vazao Jaguari - Atibainha",
            "Faixa 5": "Especial - 15,5"
        }

        regra_operacao_vazao_alto_tietê = {
            "Faixa 1": "Normal - 15,0",
        }

        html_blocks = []
        for i, row in merged_data_sistemas.iterrows():          
            bloco = f"""
                <div style="background-color:{row['cor_volume_atual']}; padding: 12px; border-radius: 8px; 
                            width: 180px; height: 80px; display: flex; flex-direction: column; 
                            justify-content: center; align-items: center; box-shadow: 3px 3px 8px rgba(0,0,0,0.4);">
                    <div style="color: black; font-size: 18px;">
                        <strong>{row['Sistema']}</strong>
                    </div>
                    <div style="color: black; font-size: 16px;">
                        {row['Volume atual (%)']:.2f}%
                    </div>
                    <div style="color: {row['cor_diferença']}; font-size: 12px;">
                        {row['diferença']:.2f} {row['simbolo']}%
                    </div>
                </div>
            """
            html_blocks.append(bloco)

        html_perc_blocks = f"""
        <div style="display: flex; flex-direction: column; align-items: center; gap: 16px; width: 100%; box-sizing: border-box;">
            <div style="display: flex; justify-content: center; gap: 16px; flex-wrap: wrap; padding: 20px;
                        width: 100%; max-width: 100%; box-sizing: border-box;">
                {''.join(html_blocks)}
            </div>
            <div style="display:flex; justify-content:center; gap:15px;">
                <div style="display:flex; align-items:center;">
                    <div style="width:15px; height:15px; background:#268b12; margin-right:5px;"></div>
                    <span style="font-size:16px;">E0 - Normal</span>
                </div>

                <div style="display:flex; align-items:center;">
                    <div style="width:15px; height:15px; background:#f8d202; margin-right:5px;"></div>
                    <span style="font-size:16px;">E1 - Atenção</span>
                </div>

                <div style="display:flex; align-items:center;">
                    <div style="width:15px; height:15px; background:#f95108; margin-right:5px;"></div>
                    <span style="font-size:16px;">E2 - Alerta</span>
                </div>

                <div style="display:flex; align-items:center;">
                    <div style="width:15px; height:15px; background:#da070f; margin-right:5px;"></div>
                    <span style="font-size:16px;">E3 - Crítico</span>
                </div>

                <div style="display:flex; align-items:center;">
                    <div style="width:15px; height:15px; background:#8435b7; margin-right:5px;"></div>
                    <span style="font-size:16px;">E4 - Emergência</span>
                </div>
            </div>
        </div>
        """

        st.components.v1.html(html_perc_blocks, height=400, scrolling=True)

        


    with map1:

        vazao_captada_diaria["date_mapa"] = pd.to_datetime(vazao_captada_diaria["dateTime"]).dt.strftime("%Y-%m-%d")
        vazao_captada_atual = vazao_captada_diaria[vazao_captada_diaria["date_mapa"] == data_atual_str]
        gdf_vazao_captada_merge = gdf_vazao_captada.merge(
            vazao_captada_atual,
            how="left",             # tipo de join
            left_on="sistema",           # coluna do shapefile
            right_on="Sistema"    # coluna do dataframe
        )


        gdfsistemas_merge = gdfsistemas.merge(
            merged_data_sistemas,
            how="left",             # tipo de join
            # left_on="sistema",           # coluna do shapefile
            # right_on="Sistema"    # coluna do dataframe
            on = "Sistema"
        )

        gdf_vazao_natural_merge = gdf_vazao_natural.merge(
            vazao_natural_diaria,
            how="left",             # tipo de join
            left_on="id",           # coluna do shapefile
            right_on="SistemaId"    # coluna do dataframe
        )

        # gdf_transposicao = gpd.read_file("data/dados_sistemas.shp")
        gdf_transposicao_merge = gdf_transposicao.merge(
            all_transferencia_final,
            how="left",             # tipo de join
            left_on="id",           # coluna do shapefile
            right_on="SistemaId"    # coluna do dataframe
        )
        # gdf_reservatorios = gpd.read_file("data/reservatorios_sabesp_sistemas.shp")
        gdf_reservatorios_merge = gdf_reservatorios.merge(
            merged_data_sistemas,
            how="left",             # tipo de join
            left_on="sistemas",           # coluna do shapefile
            right_on="Sistema"    # coluna do dataframe
        )
            
        gdf_transposicao_merge = gdf_transposicao_merge.drop(columns=["deliveredAt"])
        gdf_vazao_natural_merge = gdf_vazao_natural_merge.drop(columns=["deliveredAt"])

        gdf_transposicao_merge["dateTime"] = gdf_transposicao_merge["dateTime"].dt.strftime("%Y-%m-%d")
        gdf_vazao_natural_merge["dateTime"] = gdf_vazao_natural_merge["dateTime"].dt.strftime("%Y-%m-%d")

        # Cria o mapa centralizado no bounding box dos sistemas
        bounds = gdfsistemas.total_bounds  # [minx, miny, maxx, maxy]

        # stations_monitoramento = get_telemetric_stations(data_atual_str)

        m = folium.Map(location=[(bounds[1]+bounds[3])/2, (bounds[0]+bounds[2])/2], zoom_start=8)

        popup_columns = ["Sistema", "Volume atual (%)", 'Volume Ano Anterior (%)']

        # Adiciona cada camada
        folium.GeoJson(gdflimite, name="Limite", style_function=lambda x: {"color": "#575757", "fillColor": "#D8D8D8",  "fillOpacity": 0.2, "weight": 2}).add_to(m)
        folium.GeoJson(
            gdfsistemas_merge,
            name="Sistema",
            style_function=lambda feature: {
                "color": "#333333",
                "fillColor": feature['properties']['cor_volume_atual'],
                "fillOpacity": 0.8,
                "weight": 1
            },
            popup=folium.GeoJsonPopup(
                fields=popup_columns,  # quais colunas exibir
                aliases=["Sistema:", "Volume atual (%):", "Volume Ano Anterior (%):"],  # rótulos
                localize=True,  # formata números
                labels=True,
                style="background-color: white; color: black; border: 1px solid gray; border-radius: 5px; padding: 5px;"
            )
        ).add_to(m)
        folium.GeoJson(gdf_pariba_do_sul, name="Paraíba do Sul", style_function=lambda x: {"color": "#3f4550", "fillColor": "#747474",  "fillOpacity": 0.8,"weight": 1}).add_to(m)
        folium.GeoJson(gdf_reservatorios_merge, name="Reservatórios", style_function=lambda x: {"color": "#7caab8", "fillColor": "#7fd7f1",  "fillOpacity": 0.8,"weight": 0.5}).add_to(m)
        folium.GeoJson(gdf_hidrografia, name="Hidrografia", style_function=lambda x: {"color": "#7fd7f1", "fillColor": "#7fd7f1",  "fillOpacity": 0.8,"weight": 1}).add_to(m)
        folium.GeoJson(gdf_transposicao_merge, name="Transposição", style_function=lambda x: {"color": "#3871eb", "fillColor": "#21428a", "fillOpacity": 0.6, "weight": 1, "dashArray": "10, 5"}).add_to(m)


        fg_transposicao = folium.FeatureGroup(name="Transposição").add_to(m)
        fg_monitoramento = folium.FeatureGroup(name="Estações de Monitoramento").add_to(m)
        fg_vazao_captada = folium.FeatureGroup(name="Vazão Captada").add_to(m)

        # Adiciona popup com valor
        for _, row in gdf_transposicao_merge.iterrows():
            x, y = row.geometry.centroid.y, row.geometry.centroid.x
            valor = f"{row['value']:.1f}"
            popup_html = f"""
            <div style="
                background-color: white; 
                color: black; 
                border: 1px solid gray; 
                border-radius: 5px; 
                padding: 5px;
                font-size: 12px;
                width: 250px;
                max-width: 300px;
                white-space: normal;
            ">
                <strong>{row['Sistema']}</strong><br>
                Transferência: {row['value']:.1f} m³/s
            </div>
            """
            folium.Marker(
                location=[x, y],
                popup=popup_html,
                icon=folium.DivIcon(html=f"""
                    <div style="text-align:center;">
                    <div style="
                        font-size:12px; 
                        color:black; 
                        font-weight:bold; 
                        border-radius: 8px; 
                        background-color:white; 
                        padding:2px 6px; 
                        box-shadow: 1px 1px 3px rgba(0,0,0,0.2);
                        display:inline-flex; 
                        align-items:center; 
                        gap:4px;
                    ">
                        <i class="fa fa-water" style="color:#294c97;"></i> {valor}
                    </div>
                </div>
                """)
            ).add_to(fg_transposicao)


        for _, row in stations_monitoramento.iterrows():
            lat, lon = row.geometry.y, row.geometry.x
            valor = f"{row['read_value']:.1f}"
            popup_html = f"""
                <div style="
                    background-color: white; 
                    color: black; 
                    border: 1px solid gray; 
                    border-radius: 5px; 
                    padding: 5px;
                    font-size: 12px;
                    width: 250px;
                    max-width: 300px;
                    white-space: normal;
                ">
                    <strong>{row['station_name']}</strong><br>
                    Valor: {row['read_value']:.1f} m³/s<br>
                    Data: {row['date']}
                </div>
            """
            folium.Marker(
                location=[lat, lon],
                popup=popup_html,
                icon=folium.DivIcon(html=f"""
                    <div style="text-align:center;">
                    <div style="
                        font-size:12px; 
                        color:black; 
                        font-weight:bold; 
                        border-radius: 8px; 
                        background-color:white; 
                        padding:2px 6px; 
                        box-shadow: 3px 3px 8px rgba(0,0,0,0.4);
                        display:inline-flex; 
                        align-items:center; 
                        gap:4px;
                    ">
                        <i class="fa fa-water" style="color:#294c97;"></i> {valor}
                    </div>
                </div>
                """)
            ).add_to(fg_monitoramento)


        for _, row in gdf_vazao_captada_merge.iterrows():

            lat, lon = row.geometry.y, row.geometry.x
            valor_num = row['value']
            valor = f"{row['value']:.2f}"
            if row['sistema'] == "Cantareira":
                operacao = '<strong>Restrição</strong> = 23,0 m³/s + transp. Atibainha'
                if valor_num > 23+7.5:
                    color = "#B91C1C"
                else:
                    color = "#29972f"
            elif row['sistema'] == "Alto Tietê":
                operacao = '15,0 m³/s'
                if valor_num > 15:
                    color = "#B91C1C"
                else:
                    color = "#29972f"
            elif row['sistema'] == "Guarapiranga":
                operacao = '16,0 m³/s'
                if valor_num > 16:
                    color = "#B91C1C"
                else:
                    color = "#29972f"
            elif row['sistema'] == "Rio Grande":
                operacao = '5,6 m³/s'
                if valor_num > 5.6:
                    color = "#B91C1C"
                else:
                    color = "#29972f"
            elif row['sistema'] == "Cotia":
                operacao = '2,3 m³/s'
                if valor_num > 2.3:
                    color = "#B91C1C"
                else:
                    color = "#29972f"
            elif row['sistema'] == "São Lourenço":
                operacao = '6,4 m³/s'
                if valor_num > 6.4:
                    color = "#B91C1C"
                else:
                    color = "#29972f"
            elif row['sistema'] == "Rio Claro":
                operacao = '4,4 m³/s'
                if valor_num > 4:
                    color = "#B91C1C"
                else:
                    color = "#29972f"
            else:
                operacao = '<strong>-</strong>'
                color = "#294c97"

            popup_html = f"""
                <div style="
                    background-color: white; 
                    color: black; 
                    border: 1px solid gray; 
                    border-radius: 5px; 
                    padding: 5px;
                    font-size: 12px;
                    width: 250px;
                    max-width: 300px;
                    white-space: normal;
                ">
                    <strong>Vazão Captada</strong><br>
                    Sistema: {row['sistema']}<br>
                    Valor: {row['value']:.2f} m³/s<br>
                    Faixa de operação: {operacao}<br>
                </div>
            """
            folium.Marker(
                location=[lat, lon],
                popup=popup_html,
                icon=folium.DivIcon(html=f"""
                    <div style="text-align:center;">
                    <div style="
                        font-size:12px; 
                        color:black; 
                        font-weight:bold; 
                        border-radius: 8px; 
                        background-color:white; 
                        padding:2px 6px; 
                        box-shadow: 3px 3px 8px rgba(0,0,0,0.4);
                        display:inline-flex; 
                        align-items:center; 
                        gap:4px;
                    ">
                        <i class="fa fa-faucet" style="color:{color};"></i> {valor}
                    </div>
                </div>
                """)
            ).add_to(fg_vazao_captada)

        folium.LayerControl().add_to(m)

        st.session_state["mapa_transposicao"] = m

        m_reservatorios= m._repr_html_()
            

        css_responsivo = """
            <style>
                .folium-map {
                    width: 100% !important;
                    height: 800px !important;
                }
                .folium-container, .leaflet-container {
                    width: 100% !important;
                    height: 800px !important;
                }
            </style>
            """
        
        m.get_root().header.add_child(Element(css_responsivo))

        st.write("""
            <div style="text-align: center; color: #333333;">
                <h1  style="font-size: 20px; margin: 0; padding: 0">Reservatórios RMSP</h1>
            </div>
            """,
            unsafe_allow_html=True)
            
        st.components.v1.html(m_reservatorios, width=900, height=500)

    with map2:

        tranferencias_all_graf = transferencias_all[transferencias_all["Sistema"]==tunel_selecionado].copy()
        all_transferencia_graf = all_transferencia_final[all_transferencia_final["Sistema"]==tunel_selecionado].copy()
        graf1, graf2 = st.columns([1.0, 1.0])

        with graf1:

            total = pd.DataFrame([{
                "Mês": "Total",
                "value": tranferencias_all_graf["value"].mean()   # ou .mean(), depende do que você quer
            }])

            transferencias = pd.concat([tranferencias_all_graf, total])
            transferencias['value'] = transferencias['value'].round(1)
            transferencias.rename(columns={"value": "Média (m³/s)"}, inplace=True)
            
            n = len(transferencias)
            fill_colors = ['white']*(n-1) + ['#f0f0f0']
            font_bold = ['normal']*(n-1) + ['bold']

            fig_tgransferencia= go.Figure(
                data=[
                    go.Table(
                        columnwidth=[2, 1],
                        header=dict(
                            values=['Mês', 'Média (m³/s)'],
                            fill_color="#7c7b83",
                            line_color='white', 
                            align='center',   # horizontal
                            font=dict(color='black', size=16)
                        ),
                        cells=dict(
                            values=[transferencias[col] for col in ['Mês', 'Média (m³/s)']],
                            fill_color=[fill_colors, fill_colors],
                            line_color='lightgray',       # linhas horizontais
                            line=dict(color='white', width=0),  # linhas verticais invisíveis
                            align='center',
                            font=dict(color='black', size=14, family="Arial"),
                            font_weight=font_bold
                        )
                    )
                ]
            )

            fig_tgransferencia.update_layout(
                title=dict(
                    text=f"Transferência Mensal<br>{transferencias['Sistema'].iloc[0]}",
                    font=dict(color='black', size=16),
                    x=0.5,           # posição horizontal (0 = esquerda, 0.5 = centro, 1 = direita)
                    xanchor="center"  
                ),
                paper_bgcolor="white",   # fundo do canvas
                plot_bgcolor="white",
                height=480     # margens menores
            )

            st.plotly_chart(fig_tgransferencia)

        with graf2:

            all_transferencia_graf['value'] = all_transferencia_graf['value'].round(3)
            all_transferencia_graf.rename(columns={"value": "Vazão (m³/s)", "mes_dia":"Data" }, inplace=True)
            
            n = len(all_transferencia_graf)
            fill_colors = ['white']*(n-1) + ['#f0f0f0']
            font_bold = ['normal']*(n-1) + ['bold']

            fig_tgransferencia_all= go.Figure(
                data=[
                    go.Table(
                        columnwidth=[2, 1],
                        header=dict(
                            values=['Data', 'Vazão (m³/s)'],
                            fill_color="#7c7b83",
                            line_color='white', 
                            align='center',   # horizontal
                            font=dict(color='black', size=16)
                        ),
                        cells=dict(
                            values=[all_transferencia_graf[col] for col in ['Data', 'Vazão (m³/s)']],
                            fill_color=[fill_colors, fill_colors],
                            line_color='lightgray',       # linhas horizontais
                            line=dict(color='white', width=0),  # linhas verticais invisíveis
                            align='center',
                            font=dict(color='black', size=14, family="Arial"),
                            font_weight=font_bold
                        )
                    )
                ]
            )

            fig_tgransferencia_all.update_layout(
                title=dict(
                    text=f"Transferência Diária<br>{transferencias['Sistema'].iloc[0]}",
                    font=dict(color='black', size=16),
                    x=0.5,           # posição horizontal (0 = esquerda, 0.5 = centro, 1 = direita)
                    xanchor="center"  
                ),
                paper_bgcolor="white",   # fundo do canvas
                plot_bgcolor="white", # margens menores
                height=480      
            )

            st.plotly_chart(fig_tgransferencia_all)

    cc1, cc2 = st.columns([2.0, 2.0])
    with cc1:
        
        vazao_natural['ano'] = vazao_natural['ano'].astype(int)
        vazao_natural_atual = vazao_natural[(vazao_natural['ano'] == 2026) & (vazao_natural['Sistema']==sistema_selecionado)]

        ano_comparacao = pd.to_datetime(ano_filtro).year
        ano_atual = datetime.today().year

        vazao_natural_comparacao = vazao_natural[(vazao_natural["ano"] == ano_comparacao) & (vazao_natural['Sistema']==sistema_selecionado)]
        vazao_natural_comparacao['data_atual'] = pd.to_datetime(
            vazao_natural_comparacao['dateTime'].dt.strftime(f"{ano_atual}-%m-%d")
        )

        vazao_natural_atual['data_formatada'] = vazao_natural_atual['dateTime'].dt.strftime('%m-%Y')
        vazao_natural_comparacao['data_formatada'] = vazao_natural_comparacao['data_atual'].dt.strftime('%m-%Y')
        
        fig_vazao = go.Figure()

        fig_vazao.add_trace(go.Bar(x=vazao_natural_comparacao["data_formatada"], y=vazao_natural_comparacao['mean_value'], name='Média', marker_color="#73A158", hovertemplate='Média: %{y:.2f}<extra></extra>'))
        fig_vazao.add_trace(go.Bar(x=vazao_natural_comparacao["data_formatada"], y=vazao_natural_comparacao['min_value'], name='Mínima', marker_color="#7E82B1", hovertemplate='Mínima: %{y:.2f}<extra></extra>'))
        # fig_vazao.add_trace(go.Scatter(x=vazao_natural_atual["data_formatada"], y=vazao_natural_atual['value'], mode='lines', name='Observado', line=dict(color="#0013BE", width=2), line_shape='spline', hovertemplate='Observado: %{y:.2f}<extra></extra>'))
        x_obs = vazao_natural_atual["data_formatada"]
        y_obs = vazao_natural_atual["value"]

        if len(vazao_natural_atual) == 1:
            # Apenas um mês → mostrar ponto
            fig_vazao.add_trace(
                go.Scatter(
                    x=x_obs,
                    y=y_obs,
                    mode='markers',
                    name='Observado',
                    marker=dict(color="#0013BE", size=7),
                    hovertemplate='Observado: %{y:.2f}<extra></extra>'
                )
            )
        elif len(vazao_natural_atual) > 1:
            # Dois ou mais meses → linha + pontos
            fig_vazao.add_trace(
                go.Scatter(
                    x=x_obs,
                    y=y_obs,
                    mode='lines+markers',
                    name='Observado',
                    line=dict(color="#0013BE", width=2),
                    # marker=dict(size=6),
                    line_shape='spline',
                    hovertemplate='Observado: %{y:.2f}<extra></extra>'
                )
            )


        fig_vazao.add_trace(go.Scatter(x=vazao_natural_comparacao["data_formatada"], y=vazao_natural_comparacao['value'], mode='lines', name=f'{ano_comparacao}', line=dict(color="#A15858", width=2), line_shape='spline', hovertemplate=f'{ano_comparacao}: %{{y:.2f}}<extra></extra>'))

        fig_vazao.update_layout(
            title=dict(
                text=f"Evolução das médias mensais da Vazão Natural (m³/s) - {vazao_natural_atual['Sistema'].iloc[0]}",
                font=dict(size=20, color='black')  # tamanho e cor do título
            ),
            hovermode='x unified',
            hoverlabel=dict(
                    bgcolor='rgba(255,255,255,0.8)',
                    font_size=11,
                    font_color="black"
                ),
            barmode='overlay',
            # title_x=0.3,
            xaxis_title="",
            yaxis_title="Vazão Natural m³/s",
            plot_bgcolor='white',    # Cor de fundo do gráfico
            paper_bgcolor='white',   # Cor de fundo da área ao redor do gráfico
            font=dict(color='black'),  # Cor das fontes para preto
            title_font=dict(color='black'),  # Cor do título
            xaxis_title_font=dict(color='black'),  # Cor do título do eixo X
            yaxis_title_font=dict(color='black'), 
            legend=dict(font=dict(color='black'), orientation="h", yanchor="top", y=1.2, xanchor="center", x=0.5),
            xaxis=dict(tickfont=dict(color='black', size=14), tickangle=-45, gridcolor='lightgray', tickformat="%Y-%m-%d"),# Cor dos valores no eixo X
            yaxis=dict(tickfont=dict(color='black', size=14), gridcolor='lightgray', tickformat=".", tickmode="auto" ) 
        )

        st.plotly_chart(fig_vazao)

    with cc2:
        vazao_captada['ano'] = vazao_captada['ano'].astype(int)
        vazao_captada_atual = vazao_captada[(vazao_captada['ano'] == 2026) & (vazao_captada['Sistema']==sistema_selecionado)]

        ano_comparacao = pd.to_datetime(ano_filtro).year
        ano_atual = datetime.today().year

        vazao_captada_comparacao = vazao_captada[(vazao_captada["ano"] == ano_comparacao) & (vazao_captada['Sistema']==sistema_selecionado)]
        vazao_captada_comparacao['data_atual'] = pd.to_datetime(
            vazao_captada_comparacao['dateTime'].dt.strftime(f"{ano_atual}-%m-%d")
        )
        
        vazao_captada_atual['data_formatada'] = vazao_captada_atual['dateTime'].dt.strftime('%m-%Y')
        vazao_captada_comparacao['data_formatada'] = vazao_captada_comparacao['data_atual'].dt.strftime('%m-%Y')
        fig_vazao_captada = go.Figure()

        fig_vazao_captada.add_trace(go.Bar(x=vazao_captada_comparacao["data_formatada"], y=vazao_captada_comparacao['mean_value'], name='Média', marker_color="#72AC7E", hovertemplate='Média: %{y:.2f}<extra></extra>'))
        fig_vazao_captada.add_trace(go.Bar(x=vazao_captada_comparacao["data_formatada"], y=vazao_captada_comparacao['min_value'], name='Mínima', marker_color="#598A9E", hovertemplate='Mínima: %{y:.2f}<extra></extra>'))
        # fig_vazao_captada.add_trace(go.Scatter(x=vazao_captada_atual["data_formatada"], y=vazao_captada_atual['value'], mode='lines', name='Observado', line=dict(color="#0013BE", width=2), line_shape='spline', hovertemplate='Observado: %{y:.2f}<extra></extra>'))
        x_obs = vazao_captada_atual["data_formatada"]
        y_obs = vazao_captada_atual["value"]

        if len(vazao_captada_atual) == 1:
            # Apenas um mês → mostrar ponto
            fig_vazao_captada.add_trace(
                go.Scatter(
                    x=x_obs,
                    y=y_obs,
                    mode='markers',
                    name='Observado',
                    marker=dict(color="#0013BE", size=7),
                    hovertemplate='Observado: %{y:.2f}<extra></extra>'
                )
            )
        elif len(vazao_captada_atual) > 1:
            # Dois ou mais meses → linha + pontos
            fig_vazao_captada.add_trace(
                go.Scatter(
                    x=x_obs,
                    y=y_obs,
                    mode='lines+markers',
                    name='Observado',
                    line=dict(color="#0013BE", width=2),
                    # marker=dict(size=6),
                    line_shape='spline',
                    hovertemplate='Observado: %{y:.2f}<extra></extra>'
                )
            )
        fig_vazao_captada.add_trace(go.Scatter(x=vazao_captada_comparacao["data_formatada"], y=vazao_captada_comparacao['value'], mode='lines', name=f'{ano_comparacao}', line=dict(color="#C52F2F", width=2), line_shape='spline', hovertemplate=f'{ano_comparacao}: %{{y:.2f}}<extra></extra>'))

        fig_vazao_captada.update_layout(
            title=dict(
                text=f"Evolução das médias mensais da Vazão Captada (m³/s) - {vazao_captada_atual['Sistema'].iloc[0]}",
                font=dict(size=20, color='black')  # tamanho e cor do título
            ),
            hovermode='x unified',
            hoverlabel=dict(
                    bgcolor='rgba(255,255,255,0.8)',
                    font_size=11,
                    font_color="black"
                ),
            barmode='overlay',
            # title_x=0.3,
            xaxis_title="",
            yaxis_title="Vazão Natural m³/s",
            plot_bgcolor='white',    # Cor de fundo do gráfico
            paper_bgcolor='white',   # Cor de fundo da área ao redor do gráfico
            font=dict(color='black'),  # Cor das fontes para preto
            title_font=dict(color='black'),  # Cor do título
            xaxis_title_font=dict(color='black'),  # Cor do título do eixo X
            yaxis_title_font=dict(color='black'), 
            legend=dict(font=dict(color='black'), orientation="h", yanchor="top", y=1.2, xanchor="center", x=0.5),
            xaxis=dict(tickfont=dict(color='black', size=14), tickangle=-45, gridcolor='lightgray', tickformat="%Y-%m-%d"),# Cor dos valores no eixo X
            yaxis=dict(tickfont=dict(color='black', size=14), gridcolor='lightgray', tickformat=".", tickmode="auto" ) 
        )

        st.plotly_chart(fig_vazao_captada)

    with cc1:
        fig_volume = go.Figure()

        fig_volume.add_trace(go.Bar(x=merged_data_sistemas['Sistema'], y=merged_data_sistemas['Volume -21 dias (%)'], name='Volume -21 dias (%)', marker_color="#646968", opacity=0.6, text=merged_data_sistemas['Volume -21 dias (%)'].map(lambda v: f"{v:.1f}"), textposition='outside'))
        fig_volume.add_trace(go.Bar(x=merged_data_sistemas['Sistema'], y=merged_data_sistemas['Volume -14 dias (%)'], name='Volume -14 dias (%)', marker_color="#9699AF", opacity=0.6, text=merged_data_sistemas['Volume -14 dias (%)'].map(lambda v: f"{v:.1f}"), textposition='outside'))
        fig_volume.add_trace(go.Bar(x=merged_data_sistemas['Sistema'], y=merged_data_sistemas['Volume -7 dias (%)'], name='Volume -7 dias (%)', marker_color="#515480", opacity=0.6, text=merged_data_sistemas['Volume -7 dias (%)'].map(lambda v: f"{v:.1f}"), textposition='outside'))
        fig_volume.add_trace(go.Bar(x=merged_data_sistemas['Sistema'], y=merged_data_sistemas['Volume atual (%)'], name='Volume atual (%)', marker_color="#08138F", text=merged_data_sistemas['Volume atual (%)'].map(lambda v: f"{v:.1f}"), textposition='outside'))
        

        fig_volume.update_layout(
            title=dict(
                text=f"Evolução do Volume Útil(%) por Sistema",
                font=dict(size=20, color='black')  # tamanho e cor do título
            ),
            # barmode='stack',
            # title_x=0.3,v
            xaxis_title="",
            yaxis_title="Volume (%)",
            plot_bgcolor='white',    # Cor de fundo do gráfico
            paper_bgcolor='white',   # Cor de fundo da área ao redor do gráfico
            font=dict(color='black'),  # Cor das fontes para preto
            title_font=dict(color='black'),  # Cor do título
            xaxis_title_font=dict(color='black'),  # Cor do título do eixo X
            yaxis_title_font=dict(color='black'), 
            legend=dict(font=dict(color='black'), orientation="h", yanchor="top", y=1.2, xanchor="center", x=0.5),
            xaxis=dict(tickfont=dict(color='black', size=14), tickangle=-45, gridcolor='lightgray'),# Cor dos valores no eixo X
            yaxis=dict(tickfont=dict(color='black', size=14), gridcolor='lightgray', tickformat=".", tickmode="auto" ) 
        )

        st.plotly_chart(fig_volume)

    with cc2:
        start_sim = '2025-08-19'
        start_sim_dt = pd.to_datetime(start_sim)
        df_sim_atual= df_sim_atual_all.copy()
        df_sim_atual["dateTime"] = pd.to_datetime(df_sim_atual["dateTime"])
        df_sim_atual = df_sim_atual[df_sim_atual['Sistema']=="SIM"]
        
        df_sim_atual_filtrado=df_sim_atual[df_sim_atual["dateTime"] >= start_sim_dt]

        data_atual_1meses = datetime.today() + relativedelta(months=1)

        projecao_sim = pd.read_csv("serie_diaria.csv")
        projecao_sim["Data"] = pd.to_datetime(projecao_sim["Data"])
        projecao_sim =  projecao_sim[projecao_sim["Data"] <= data_atual_1meses]

        colunas = ['QN100 (20-25)', 'QN100 MLT', 'QN70 MLT', 'QN (2021)', 'QN (2014)']
        colunas = ['QN 100 MLT','QN 70 MLT','QN (20-25)','QN (2021)','QN (2014)','QN (2020)']
        for c in colunas:
            projecao_sim[c] = pd.to_numeric(projecao_sim[c], errors='coerce')
            projecao_sim[c].fillna(0, inplace=True)

        projecao_sim['data_formatada'] = projecao_sim['Data'].dt.strftime('%d-%m-%Y')
        df_sim_atual_filtrado['data_formatada']=df_sim_atual_filtrado["dateTime"].dt.strftime('%d-%m-%Y')
        
        fig_sim = go.Figure()

        fig_sim.add_trace(go.Scatter(x=df_sim_atual_filtrado["data_formatada"], y=df_sim_atual_filtrado['value'], mode='lines', name='Observado', line=dict(color="#111311", width=2), line_shape='spline', hovertemplate='Observado: %{y:.2f}<extra></extra>'))

        fig_sim.add_trace(go.Scatter(x=projecao_sim["data_formatada"], y=projecao_sim['QN (20-25)'], 
                                    mode='lines', name='QN (20-25)', line=dict( color="#387540", width=1.5)))
            
        fig_sim.add_trace(go.Scatter(x=projecao_sim["data_formatada"], y=projecao_sim['QN 100 MLT'], 
                                    mode='lines', name='QN 100 MLT', line=dict(color="#416ee7", width=1.5)))

        fig_sim.add_trace(go.Scatter(x=projecao_sim["data_formatada"], y=projecao_sim['QN 70 MLT'], 
                                    mode='lines', name='QN 70 MLT', line=dict(color="#9c2626", width=1.5)))

        fig_sim.add_trace(go.Scatter(x=projecao_sim["data_formatada"], y=projecao_sim['QN (2021)'], 
                                    mode='lines', name='QN (2021)', line=dict(dash='dash', color="#5EB16B", width=1.5)))
        
        fig_sim.add_trace(go.Scatter(x=projecao_sim["data_formatada"], y=projecao_sim['QN (2014)'], 
                                    mode='lines', name='QN (2014)', line=dict(dash='dash', color="#c06906", width=1.5)))
        
        fig_sim.add_trace(go.Scatter(x=projecao_sim["data_formatada"], y=projecao_sim['QN (2020)'], 
                                    mode='lines', name='QN (2020)', line=dict(dash='dash', color="#aa04c0", width=1.5)))


        # Atualizando o layout do gráfico
        fig_sim.update_layout(
            title=dict(
                text="Projeção de Volume do SIM",
                font=dict(size=20, color='black')  # tamanho e cor do título
            ),
            # title_x=0.3,
            hovermode='x unified',
            hoverlabel=dict(
                    bgcolor='rgba(255,255,255,0.8)',
                    font_size=11,
                    font_color="black"
                ),
            xaxis_title="",
            yaxis_title="Volume (%)",
            plot_bgcolor='white',    # Cor de fundo do gráfico
            paper_bgcolor='white',   # Cor de fundo da área ao redor do gráfico
            font=dict(color='black'),  # Cor das fontes para preto
            title_font=dict(color='black'),  # Cor do título
            xaxis_title_font=dict(color='black'),  # Cor do título do eixo X
            yaxis_title_font=dict(color='black'), 
            legend=dict(font=dict(color='black'), orientation="h", yanchor="top", y=1.2, xanchor="center", x=0.5),
            xaxis=dict(tickfont=dict(color='black', size=14), tickangle=-45, gridcolor='lightgray', tickformat="%Y-%m-%d"),# Cor dos valores no eixo X
            yaxis=dict(tickfont=dict(color='black', size=14), gridcolor='lightgray', tickformat=".", tickmode="auto" ) 
        )

        st.plotly_chart(fig_sim)
    vazao_descarregada_cantareira = vazao_descarregada[vazao_descarregada['Sistema'] == 'Cantareira']
    media_movel_captada = calculate_media_movel_captda(df_sim_atual_all, vazao_captada_diaria, vazao_afluente, vazao_descarregada_cantareira, sistema_selecionado)
    

    media_movel_captada_all= media_movel_captada.rename(columns={"MediaMovel_Vazão Captada_14d":"MediaMovel_Vazão_Captada_14d", f"MediaMovel_Vazão Afluente {sistema_selecionado}_14d": f"MediaMovel_Vazão_Afluente {sistema_selecionado}_14d"})
    data_inicio = pd.to_datetime("2025-08-01")
    media_movel_captada = media_movel_captada_all[media_movel_captada_all['dateTime'] >= data_inicio]

    # media_movel_captada['data_formatada'] = media_movel_captada['dateTime'].dt.strftime('%d-%m-%Y')

    data_ref = pd.to_datetime("2025-08-27").to_pydatetime()
    data_ref_filtro = pd.to_datetime("2025-08-27")
    idx_captada = (media_movel_captada['dateTime'] - data_ref_filtro).abs().idxmin()
    idx_afluente = (media_movel_captada['dateTime'] - data_ref_filtro).abs().idxmin()
    idx_taxa = (media_movel_captada['dateTime'] - data_ref_filtro).abs().idxmin()

    data_ref_2 = pd.to_datetime("2025-08-13").to_pydatetime()
    data_ref_filtro_2 = pd.to_datetime("2025-08-13")
    idx_captada_2 = (media_movel_captada['dateTime'] - data_ref_filtro_2).abs().idxmin()
    idx_afluente_2 = (media_movel_captada['dateTime'] - data_ref_filtro_2).abs().idxmin()
    idx_taxa_2 = (media_movel_captada['dateTime'] - data_ref_filtro_2).abs().idxmin()

    data_ref_3 = pd.to_datetime("2025-09-22").to_pydatetime()
    data_ref_filtro_3 = pd.to_datetime("2025-09-22")
    idx_captada_3 = (media_movel_captada['dateTime'] - data_ref_filtro_3).abs().idxmin()
    idx_afluente_3 = (media_movel_captada['dateTime'] - data_ref_filtro_3).abs().idxmin()
    idx_taxa_3 = (media_movel_captada['dateTime'] - data_ref_filtro_3).abs().idxmin()

    ultima_data = media_movel_captada['dateTime'].max()
    valor_captada_final = media_movel_captada.loc[media_movel_captada['dateTime'] == ultima_data, 'MediaMovel_Vazão_Captada_14d'].values[0]
    valor_afluente_final = media_movel_captada.loc[media_movel_captada['dateTime'] == ultima_data, f'MediaMovel_Vazão_Afluente {sistema_selecionado}_14d'].values[0]
    valor_taxa_final = media_movel_captada.loc[media_movel_captada['dateTime'] == ultima_data, 'TaxaVar_14d'].values[0]

    valor_captada = media_movel_captada.loc[idx_captada, 'MediaMovel_Vazão_Captada_14d']
    valor_afluente = media_movel_captada.loc[idx_afluente, f'MediaMovel_Vazão_Afluente {sistema_selecionado}_14d']
    valor_taxa = media_movel_captada.loc[idx_taxa, 'TaxaVar_14d']

    valor_taxa_min = media_movel_captada['TaxaVar_14d'].min() - 0.15
    valor_taxa_max = media_movel_captada['TaxaVar_14d'].max()

    if valor_taxa_max < 0:
        valor_taxa_max = 0
    else:
        valor_taxa_max = valor_taxa_max + 0.10

    valor_captada_2 = media_movel_captada.loc[idx_captada_2, 'MediaMovel_Vazão_Captada_14d']
    valor_afluente_2 = media_movel_captada.loc[idx_afluente_2, f'MediaMovel_Vazão_Afluente {sistema_selecionado}_14d']
    media_movel_captada['TaxaVar_14d'] = media_movel_captada['TaxaVar_14d'].replace({np.nan: None})
    valor_taxa_2 = media_movel_captada.loc[idx_taxa_2, 'TaxaVar_14d']

    valor_captada_3 = media_movel_captada.loc[idx_captada_3, 'MediaMovel_Vazão_Captada_14d']
    valor_afluente_3 = media_movel_captada.loc[idx_afluente_3, f'MediaMovel_Vazão_Afluente {sistema_selecionado}_14d']
    media_movel_captada['TaxaVar_14d'] = media_movel_captada['TaxaVar_14d'].replace({np.nan: None})
    valor_taxa_3 = media_movel_captada.loc[idx_taxa_3, 'TaxaVar_14d']
    
    if sistema_selecionado == "São Lourenço":
        intervalo = 0.5
    else:
        intervalo = 0.05

    # media_movel_captada['data_formatada'] = media_movel_captada['dateTime'].dt.strftime('%d-%m-%Y')
    fig_media_movel_sim = go.Figure()
    fig_media_movel_sim.add_trace(go.Scatter(x=media_movel_captada["dateTime"], y=media_movel_captada['MediaMovel_Vazão_Captada_14d'], mode='lines', name='Media Movel Vazão Captada(14d)', line=dict(color="#232FE0", width=1.5), line_shape='spline', hovertemplate='Média Movel Vazão Captada(14d): %{y:.2f}<extra></extra>'))
    fig_media_movel_sim.add_trace(go.Scatter(x=media_movel_captada["dateTime"], y=media_movel_captada[f'MediaMovel_Vazão_Afluente {sistema_selecionado}_14d'], mode='lines', name=f'Media Movel Vazão Afluente {sistema_selecionado} (14d)', line=dict( color="#387540", width=1.5), hovertemplate='Média Movel Vazão Afluente(14d): %{y:.2f}<extra></extra>'))         
    fig_media_movel_sim.add_trace(go.Scatter(x=media_movel_captada["dateTime"], y=media_movel_captada['TaxaVar_14d'], mode='lines', name='TaxaVar Var. 14d', line=dict(dash='dash', color="#c47003", width=1.5), yaxis="y2", hovertemplate='TaxaVar Var. 14d: %{y:.2f}<extra></extra>'))
    fig_media_movel_sim.add_trace(go.Scatter(x=[None], y=[None],mode="lines",line=dict(color="#da1010", width=2),name=f"Ref: {data_ref_2.strftime('%d/%m/%Y')} (Início da RDA)"))
    fig_media_movel_sim.add_trace(go.Scatter(x=[None], y=[None],mode="lines",line=dict(color="#6e0808", width=2),name=f"{data_ref.strftime('%d/%m/%Y')} (Início da GDN)"))
    fig_media_movel_sim.add_trace(go.Scatter(x=[None], y=[None],mode="lines",line=dict(color="#8917be", width=2),name=f"Ref: {data_ref_3.strftime('%d/%m/%Y')} (Início da GDN 10h)"))
    
    fig_media_movel_sim.add_vline(x=data_ref, line=dict(color="#6e0808", width=2, dash="solid"))
    fig_media_movel_sim.add_vline(x=data_ref_2, line=dict(color="#da1010", width=2, dash="solid"))
    fig_media_movel_sim.add_vline(x=data_ref_3, line=dict(color="#8917be", width=2, dash="solid"))

    fig_media_movel_sim.add_annotation(x=data_ref, y=valor_captada,text=f"{valor_captada:.2f}", font=dict(color="#232FE0", size=18), showarrow=True, arrowcolor="#232FE0", arrowhead=2, ax=-40, ay=-40)
    fig_media_movel_sim.add_annotation(x=data_ref_2,y=valor_captada_2,text=f"{valor_captada_2:.2f}", font=dict(color="#232FE0", size=18), showarrow=True,arrowcolor="#232FE0",arrowhead=2,ax=-40,ay=-40)
    fig_media_movel_sim.add_annotation(x=data_ref_3,y=valor_captada_2,text=f"{valor_captada_3:.2f}", font=dict(color="#232FE0", size=18), showarrow=True,arrowcolor="#232FE0",arrowhead=2,ax=-40,ay=-40)

    fig_media_movel_sim.add_annotation(x=data_ref,y=valor_afluente,text=f"{valor_afluente:.2f}", font=dict(color="#387540", size=18), showarrow=True,arrowcolor="#387540",arrowhead=2,ax=-40,ay=-40)
    fig_media_movel_sim.add_annotation(x=data_ref_2,y=valor_afluente_2,text=f"{valor_afluente_2:.2f}", font=dict(color="#387540", size=18), showarrow=True,arrowcolor="#387540",arrowhead=2,ax=-40,ay=-40)
    fig_media_movel_sim.add_annotation(x=data_ref_3,y=valor_afluente_3,text=f"{valor_afluente_3:.2f}", font=dict(color="#387540", size=18), showarrow=True,arrowcolor="#387540",arrowhead=2,ax=-40,ay=-40)

    fig_media_movel_sim.add_annotation(x=data_ref,y=valor_taxa,text=f"{valor_taxa:.2f}", font=dict(color="#c47003", size=18), showarrow=True,arrowcolor="#c47003",arrowhead=2,ax=-40,ay=-40,yref="y2")
    fig_media_movel_sim.add_annotation(x=data_ref_2,y=valor_taxa_2,text=f"{valor_taxa_2:.2f}", font=dict(color="#c47003", size=18), showarrow=True,arrowcolor="#c47003",arrowhead=2,ax=-40,ay=-40,yref="y2")
    fig_media_movel_sim.add_annotation(x=data_ref_3,y=valor_taxa_3,text=f"{valor_taxa_3:.2f}", font=dict(color="#c47003", size=18), showarrow=True,arrowcolor="#c47003",arrowhead=2,ax=-40,ay=-40,yref="y2")


    # Anotação da vazão captada
    fig_media_movel_sim.add_annotation(
        x=ultima_data,
        y=valor_captada_final,
        text=f"{valor_captada_final:.2f}",
        showarrow=False,       # sem seta
        xanchor="left",        # fica à direita da linha
        yanchor="middle",
        font=dict(color="#232FE0", size=16)
    )

    # Anotação da vazão afluente
    fig_media_movel_sim.add_annotation(
        x=ultima_data,
        y=valor_afluente_final,
        text=f"{valor_afluente_final:.2f}",
        showarrow=False,
        xanchor="left",
        yanchor="middle",
        font=dict(color="#387540", size=16)
    )

    # Anotação da taxa de variação (segundo eixo)
    fig_media_movel_sim.add_annotation(
        x=ultima_data,
        y=valor_taxa_final,
        text=f"{valor_taxa_final:.2f}",
        showarrow=False,
        xanchor="left",
        yanchor="middle",
        font=dict(color="#c47003", size=16),
        yref="y2"   # importante: segundo eixo
    )

    # Atualizando o layout do gráfico
    fig_media_movel_sim.update_layout(
        title=dict(
            text=f"Médias Móveis das Vazões - {sistema_selecionado}",
            font=dict(size=20, color='black')
        ),
        hovermode='x unified',
        hoverlabel=dict(
                bgcolor='rgba(255,255,255,0.8)',
                font_size=11,
                font_color="black"
            ),
        xaxis=dict(
            title="",
            tickfont=dict(color='black', size=16),
            tickangle=-45,
            gridcolor='lightgray',
            tickformat="%Y-%m-%d"
        ),
        yaxis=dict(
            title=dict(
                text="Médias Móveis das Vazões (m³/s)",
                font=dict(color="#111311")
            ),
            tickfont=dict(color='black', size=16),
            gridcolor='lightgray'
        ),
        yaxis2=dict(
            title=dict(
                text="Taxa de variação de volume útil (%)",
                font=dict(color="#c47003")
            ),
            overlaying="y",
            side="right",
            tickfont=dict(color="#c47003", size=16),
            gridcolor="#FFFFFF",
            range=[valor_taxa_min, valor_taxa_max],
            dtick=intervalo,
            fixedrange=True,
            zeroline=False 
        ),
        plot_bgcolor='white',
        paper_bgcolor='white',
        font=dict(color='black'),
        height=700,
        legend=dict(
            font=dict(color='black', size=16),
            orientation="h",
            yanchor="top",
            y=1.1,
            xanchor="center",
            x=0.5
        )
    )
    fig_media_movel_sim.update_xaxes(tickformat="%d-%m-%Y")

    st.plotly_chart(fig_media_movel_sim)
    vazao_descarregada['value'] = vazao_descarregada['value'].round(3)
    pivot_vazao_descarregada = vazao_descarregada.pivot(
        index=['dateTime', 'Mês', 'mes_n'],  # adiciona Mês ao índice
        columns='Sistema',
        values='value'
    ).reset_index()

    cd1, cd2 = st.columns([2.00, 2.00])

    with cd1:

        pivot_vazao_descarregada['dateTime'] = pd.to_datetime(pivot_vazao_descarregada['dateTime'])

        pivot_vazao_descarregada_atual = pivot_vazao_descarregada[
            (pivot_vazao_descarregada['dateTime'].dt.month == pd.Timestamp.today().month) &
            (pivot_vazao_descarregada['dateTime'].dt.year == pd.Timestamp.today().year)
        ].copy()

        pivot_vazao_descarregada_atual['Data'] = pivot_vazao_descarregada_atual['dateTime'].dt.strftime('%d/%m/%Y')
        cols_sistemas = ['Cantareira', 'Atibainha', 'Cachoeira', 'Jaguari / Jacareí', 'Paiva Castro']

        for col in cols_sistemas:
            pivot_vazao_descarregada_atual[col] = pivot_vazao_descarregada_atual[col].map(lambda x: f"{x:.2f}")

        n = len(pivot_vazao_descarregada_atual)
        fill_colors = ['white']*(n-1) + ["#cac9c9"]
        font_bold = ['normal']*(n-1) + ['bold']

        fig_tgransferencia_all= go.Figure(
            data=[
                go.Table(
                    columnwidth=[1.3, 1.3, 1.3, 1.3, 2.0, 1.7],
                    header=dict(
                        values=['Data', 'Cantareira', 'Atibainha', 'Cachoeira', 'Jaguari / Jacareí', 'Paiva Castro'],
                        fill_color="#f3f3f3",
                        line_color='white', 
                        align='center',   # horizontal
                        font=dict(color='black', size=16)
                    ),
                    cells=dict(
                        values=[pivot_vazao_descarregada_atual[col] for col in ['Data', 'Cantareira', 'Atibainha', 'Cachoeira', 'Jaguari / Jacareí', 'Paiva Castro']],
                        fill_color=[fill_colors, fill_colors],
                        line_color='lightgray',       # linhas horizontais
                        line=dict(color='white', width=0),  # linhas verticais invisíveis
                        align='center',
                        font=dict(color='black', size=14, family="Arial"),
                        font_weight=font_bold
                    )
                )
            ]
        )

        fig_tgransferencia_all.update_layout(
            title=dict(
                text=f"Vazão Descarregada (m³/s) - Diária",
                font=dict(color='black', size=16),
                x=0.5,           # posição horizontal (0 = esquerda, 0.5 = centro, 1 = direita)
                xanchor="center",
                y=0.90,       # posição vertical (0 = fundo, 1 = topo)
                yanchor="top"  
            ),
            paper_bgcolor="white",   # fundo do canvas
            plot_bgcolor="white",
            width=1300,   # largura total
            height=480    # altura total da figura     # margens menores
        )

        st.plotly_chart(fig_tgransferencia_all, use_container_width=True)


    with cd2:

        pivot_vazao_descarregada['dateTime'] = pd.to_datetime(pivot_vazao_descarregada['dateTime'])

        pivot_vazao_descarregada_atual = pivot_vazao_descarregada[
            (pivot_vazao_descarregada['dateTime'].dt.year == pd.Timestamp.today().year)
        ].copy()

        cols_sistemas = ['Cantareira', 'Atibainha', 'Cachoeira', 'Jaguari / Jacareí', 'Paiva Castro']

        group_vazao_descarregada = pivot_vazao_descarregada_atual.groupby(['mes_n', 'Mês'])[cols_sistemas].mean().reset_index()
        group_vazao_descarregada = group_vazao_descarregada.sort_values('mes_n').reset_index(drop=True)

        total = pd.DataFrame([{
            "Mês": "Total",
            "Cantareira": group_vazao_descarregada['Cantareira'].mean(),
            "Atibainha": group_vazao_descarregada['Atibainha'].mean(),
            "Cachoeira": group_vazao_descarregada['Cachoeira'].mean(),
            "Jaguari / Jacareí": group_vazao_descarregada['Jaguari / Jacareí'].mean(),
            "Paiva Castro": group_vazao_descarregada['Paiva Castro'].mean()
        }])

        for col in cols_sistemas:
            group_vazao_descarregada[col] = group_vazao_descarregada[col].map(lambda x: f"{x:.2f}")
            total[col] = f"{total[col][0]:.2f}"

        display_table = pd.concat([group_vazao_descarregada, total], ignore_index=True)

        n = len(display_table)
        fill_colors = ['white']*(n-1) + ["#cac9c9"]
        font_bold = ['normal']*(n-1) + ['bold']

        fig_tgransferencia_all= go.Figure(
            data=[
                go.Table(
                    columnwidth=[1.3, 1.3, 1.3, 1.3, 2.0, 1.7],
                    header=dict(
                        values=['Mês', 'Cantareira', 'Atibainha', 'Cachoeira', 'Jaguari / Jacareí', 'Paiva Castro'],
                        fill_color="#f3f3f3",
                        line_color='white', 
                        align='center',   # horizontal
                        font=dict(color='black', size=16)
                    ),
                    cells=dict(
                        values=[display_table[col] for col in ['Mês', 'Cantareira', 'Atibainha', 'Cachoeira', 'Jaguari / Jacareí', 'Paiva Castro']],
                        fill_color=[fill_colors, fill_colors],
                        line_color='lightgray',       # linhas horizontais
                        line=dict(color='white', width=0),  # linhas verticais invisíveis
                        align='center',
                        font=dict(color='black', size=14, family="Arial"),
                        font_weight=font_bold
                    )
                )
            ]
        )

        fig_tgransferencia_all.update_layout(
            title=dict(
                text=f"Vazão Média Descarregada (m³/s) - Mensal",
                font=dict(color='black', size=16),
                x=0.5,           # posição horizontal (0 = esquerda, 0.5 = centro, 1 = direita)
                xanchor="center",
                y=0.90,       # posição vertical (0 = fundo, 1 = topo)
                yanchor="top"  
            ),
            paper_bgcolor="white",   # fundo do canvas
            plot_bgcolor="white",
            width=1300,   # largura total
            height=480    # altura total da figura     # margens menores
        )

        st.plotly_chart(fig_tgransferencia_all, use_container_width=True)


    co1, co2 = st.columns([1.50, 0.50])

    with co1:
        gov_base64 = get_base64_image("regua.png")
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
            <div style="position: absolute; bottom: -100px; right: -380px; display: flex; gap: 20px; z-index: 1;">
                <img src="data:image/png;base64,{gov_base64}" width="600" height="80">
            </div>
            """,
            unsafe_allow_html=True
        )

def capturar_tela(url):

    driver, dir_path = iniciar_chrome_com_diretorio_unico()
    try:
        driver.get(url)

        tm.sleep(2)
        
        # Descobrir largura e altura máxima da página com JavaScript
        largura = driver.execute_script("return document.body.scrollWidth")
        altura = driver.execute_script("return document.body.scrollHeight")

        # Redimensionar a janela para o tamanho total
        driver.set_window_size(largura, altura)

        tm.sleep(1)  # Pequena espera para renderizar com o novo tamanho

        screenshot = driver.get_screenshot_as_png()
        
    finally:
        driver.quit()
        shutil.rmtree(dir_path, ignore_errors=True)
    
    imagem = Image.open(io.BytesIO(screenshot))
    
    return imagem


# CSS personalizado para fundo branco e estilo dos slides
st.markdown(
    """
    <style>
    /* Limita a largura máxima do contêiner para evitar overflow */
    .main .block-container {
        max-width: 100%;  /* Ajuste para garantir a largura adequada */
    }
    .stApp .block-container {
        height: 80vh; 
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

    div.stButton > button:first-child {
        background-color: #FFFFFF;  /* Fundo branco */
        color: #000000;           /* Texto preto */
        border: 1px solid #CCCCCC; /* Borda cinza */
        font-weight: normal;      /* Peso da fonte (opcional) */
    }
    
    /* Efeito hover (opcional) */
    div.stButton > button:first-child:hover {
        background-color: #F5F5F5;  /* Cor ao passar o mouse */
    }

    textarea {
        font-size: 15px !important;
    }
    .stDownloadButton>button {
        background-color: transparent !important;
        border: 1px solid #ffffff !important;
        color: white !important;
    }

    .stDownloadButton>button:hover {
        background-color: rgba(255, 255, 255, 0.1) !important;
    }

    /* Container principal - reforço de especificidade */
    div[data-baseweb="select"] div {
        color: #000000 !important;
    }

    /* Caixa principal do select */
    div[data-baseweb="select"] > div {
        background-color: #FFFFFF !important;
        border: 1px solid #CCCCCC !important;
        border-radius: 4px !important;
    }

    /* Texto do placeholder (quando vazio) - abordagem agressiva */
    div[data-baseweb="select"] > div > div > div[aria-hidden="true"],
    div[data-baseweb="select"] > div > div > div:first-child {
        color: #000000 !important;
    }

    /* Texto digitado (busca) - abordagem direta */
    div[data-baseweb="select"] input {
        color: #000000 !important;
        caret-color: #000000 !important; /* Cor do cursor de texto */
    }

    /* Ícones */
    div[data-baseweb="select"] svg {
        fill: #000000 !important;
    }

    /* Itens selecionados (tags) */
    div[data-baseweb="select"] span[role="button"] {
        color: #000000 !important;
        background-color: #f0f0f0 !important;
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
                <h1  style="font-size: 18px;">Mapa de dias secos </h1>
            </div>
            """,
            unsafe_allow_html=True)

        query_dias_sem_chuva = f"""select 
                                    c.cod_ibge,
                                    c."name",
                                    SUM(hs.dsc) AS dsc
                                from hidroapp_statistics hs 
                                left join cities c on c.id = hs.model_id
                                where date_hour between '2025-04-01 03:00:00.000' and '2025-09-30 03:00:00.000'and model_type ='City'
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
            cs_chuva_10=('dcsc_chuva', lambda x: x[(x >= 5) & (x < 10)].count()),
            cs_chuva_30=('dcsc_chuva', lambda x: x[(x >= 10) & (x < 30)].count()),
            cs_chuva_50=('dcsc_chuva', lambda x: x[(x >= 30) & (x < 50)].count()),
            cs_chuva_80=('dcsc_chuva', lambda x: x[(x >= 50) & (x < 80)].count()),
            cs_chuva_120=('dcsc_chuva', lambda x: x[(x >= 80) & (x < 120)].count()),
            cs_chuva_121=('dcsc_chuva', lambda x: x[x >= 120].count())
        )

        tabela_df['cs_chuva'] = tabela_df['cs_chuva'].astype(float)        

        shapefile_path = "data/DIV_MUN_SP_2021a.shp"
        gdf = gpd.read_file(shapefile_path)
        gdf["geometry"] = gdf["geometry"].simplify(tolerance=0.01, preserve_topology=True)

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
                    <div style="width: 50px; height: 15px; background-color: #8ff29b; display: flex; align-items: center; justify-content: center; color: #2E2E2E; font-size: 8px; border-radius: 3px;">
                        <span> 10 >< 30 </span>
                    </div>   
                </div>
                <div style="display: flex; align-items: center; margin-right: 5px;">
                    <div style="width: 50px; height: 15px; background-color: #5ab53c; display: flex; align-items: center; justify-content: center; color: #2E2E2E; font-size: 8px; border-radius: 3px;">
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

            zoom_css = """
            <style>
                body {
                    zoom: 1.5;
                }
            </style>
            """

            # Insere no <head> do HTML do Folium
            mapa_dsc.get_root().header.add_child(Element(zoom_css))

            mapa_dsc.save("mapa_html_dsc.html")

            css_responsivo = """
                <style>
                .folium-map {
                    width: 100% !important;
                    height: 100% !important;
                }
                .folium-container, .leaflet-container {
                    width: 100% !important;
                    height: auto !important;
                }
                </style>
            """
            mapa_dsc.get_root().header.add_child(Element(css_responsivo))

            st.write("""
                <div style="text-align: center; color: #333333;">
                    <h1  style="font-size: 14px; margin: 0; padding: 0">Dias sem chuva no período de estiagem (01/04 a 30/09)</h1>
                </div>
                """,
            unsafe_allow_html=True)
            st.components.v1.html(mapa_html_dsc, height=500)

            url_geodados='https://hidroapp.daee.sp.gov.br/mapa'
            st.write(f"""
                <div style="color: black; line-height: 1;">
                    <p style="text-align: center; font-size: 12px; margin: 0; padding: 0;">Elaborado pela equipe do SP Águas. Disponível em: <a href="{url_geodados}" target="_blank"> Hidroapp</a></p>
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

            zoom_css = """
            <style>
                body {
                    zoom: 1.5;
                }
            </style>
            """

            # Insere no <head> do HTML do Folium
            mapa.get_root().header.add_child(Element(zoom_css))
            mapa.save("mapa_html_dcsc.html")

            css_responsivo = """
                <style>
                    .folium-map {
                        width: 100% !important;
                        height: 100% !important;
                    }
                    .folium-container, .leaflet-container {
                        width: 100% !important;
                        height: auto !important;
                    }
                </style>
                """
            mapa.get_root().header.add_child(Element(css_responsivo))

            st.write("""
                <div style="text-align: center; color: #333333;">
                    <h1  style="font-size: 14px; margin: 0; padding: 0">Dias consecutivos sem chuva</h1>
                </div>
                """,
            unsafe_allow_html=True)
            st.components.v1.html(mapa_html, height=500)
            url_geodados='https://hidroapp.daee.sp.gov.br/mapa'
            st.write(f"""
                <div style="color: black; line-height: 1;">
                    <p style="text-align: center; font-size: 12px; margin: 0; padding: 0;">Elaborado pela equipe do SP Águas. Disponível em: <a href="{url_geodados}" target="_blank"> Hidroapp</a></p>
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
            
            user_input = st.text_area("Relatos 24h", height=200, key="user_input_slide1_seca")
                   
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

            html_tabela = styled_df.to_html()
            # html_tabela.save("tabela_slide1.html")

            os.makedirs("imagens", exist_ok=True)
            caminho_imagem = "imagens/tabela_dsc.png"
            if os.path.exists(caminho_imagem):
                os.remove(caminho_imagem)

            soup = BeautifulSoup(html_tabela, 'html.parser')
            caption = soup.find('caption')
            if caption:
                caption.decompose() 

            html_sem_titulo = str(soup)

            hti = Html2Image(
                    custom_flags=[
                    "--headless=new",
                    "--disable-gpu",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--force-device-scale-factor=3"
                ]
            )
            hti.output_path = "imagens"
            chrome_path = localizar_chrome()
            hti.browser_path = chrome_path
            hti.screenshot(html_str=html_sem_titulo, save_as='tabela_dsc.png', size=(700, 500))
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

            html_tabela = styled_df.to_html()
            # html_tabela.save("tabela_slide1.html")

            os.makedirs("imagens", exist_ok=True)
            caminho_imagem = "imagens/tabela_dcsc.png"
            if os.path.exists(caminho_imagem):
                os.remove(caminho_imagem)

            soup = BeautifulSoup(html_tabela, 'html.parser')
            caption = soup.find('caption')
            if caption:
                caption.decompose() 

            html_sem_titulo = str(soup)

            hti = Html2Image(
                custom_flags=[
                "--headless=new",
                "--disable-gpu",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--force-device-scale-factor=3"
                ]
            )
            hti.output_path = "imagens"

            chrome_path = localizar_chrome()
            hti.browser_path = chrome_path
            hti.screenshot(html_str=html_sem_titulo, save_as='tabela_dcsc.png', size=(700, 500))
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
                '<30': '#5ab53c',
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
            margin=dict(t=60, b=140, l=60, r=40),
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

        os.makedirs("imagens", exist_ok=True)
        caminho_imagem = "imagens/grafico_dcsc_ugrhi.png"
        if os.path.exists(caminho_imagem):
            os.remove(caminho_imagem)

        fig.update_layout(title_text="")  # Remove o título

        html_str = fig.to_html(full_html=False, include_plotlyjs='cdn')
        hti = Html2Image(
            custom_flags=[
                "--headless=new",
                "--disable-gpu",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--force-device-scale-factor=3"
            ]
        )
        hti.output_path = "imagens"
        chrome_path = localizar_chrome()
        hti.browser_path = chrome_path
        hti.screenshot(html_str=html_str, save_as=f'grafico_dcsc_ugrhi.png', size=(1400, 1000))


        return user_input


async def slide1():
    
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
                <h1  style="font-size: 18px;">Dados Pluviometria</h1>
            </div>
            """,
            unsafe_allow_html=True)


        coluna1, coluna2 = st.columns([1.0, 1.0])

        cmap1, cmap2, cmap3 = st.columns([0.5, 1.0, 0.5])

        colun1, colun2, colun3 = st.columns([0.2, 1.2, 0.2])

        data_ini, data_fim = st.session_state.get("intervalo", (None, None))

        data_inicial = datetime.today()
        hora_inicial = time(10, 0)
        data_hora_inicial = datetime.combine(data_inicial, hora_inicial)
        data_inicial_str = data_hora_inicial.strftime('%Y-%m-%d')
        hora_inicial_str = data_hora_inicial.strftime('%H:%M')
       

        url = f'https://cth.daee.sp.gov.br/sibh/api/v2/measurements/now?station_type_id=2&hours=24&from_date={data_inicial_str}T{hora_inicial_str}&serializer=complete&public=true'
        
        response = requests.get(url)

        if response.status_code == 200:

            data = response.json()

            if 'measurements' in data and data['measurements']:
                
                df = pd.DataFrame(data['measurements'])

                df['value'] = pd.to_numeric(df['value'], errors='coerce')
                df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce')
                df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')
                df = df.sort_values(by="value", ascending=False)
                
                prefix_list = sorted(df['prefix'].dropna().unique().tolist())

                if 'excluir_prefixos' not in st.session_state:
                    st.session_state.excluir_prefixos = []

                # Aplica o filtro, se houver exclusões
                if st.session_state.excluir_prefixos:
                    df = df[~df['prefix'].isin(st.session_state.excluir_prefixos)]
                
                latitude =  -22.8859
                longitude = -48.4451

                shapefile_path = "data/limiteestadualsp.shp"
                gdf = gpd.read_file(shapefile_path)

                mapa = folium.Map(
                    location=[latitude, longitude],  # Centralizar no meio dos pontos
                    zoom_start=6,
                    tiles=None,
                    control_scale=False, 
                    zoomControl=False,
                )

                # folium.TileLayer(
                #     tiles='https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
                #     attr=' ',
                #     name='OpenStreetMap',
                #     overlay=False,
                #     control=True, 
                # ).add_to(mapa)

                folium.TileLayer(
                    tiles='https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
                    attr='CartoDB',
                    name='CartoDB Light',
                ).add_to(mapa)

                mapa.options['attributionControl'] = False

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
                                popup=popup,
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
                                popup=popup,
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
                                popup=popup,
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

                mapa_html_flu = mapa._repr_html_()
                zoom_css = """
                <style>
                    body {
                        zoom: 1.5;
                    }
                </style>
                """

                # Insere no <head> do HTML do Folium
                mapa.get_root().header.add_child(Element(zoom_css))
                mapa.save("mapa_html_flu.html")

                css_responsivo = """
                    <style>
                        .folium-map {
                            width: 100% !important;
                            height: 100% !important;
                        }
                        .folium-container, .leaflet-container {
                            width: 100% !important;
                            height: 100% !important;
                        }
                    </style>
                    """
                mapa.get_root().header.add_child(Element(css_responsivo))

                with coluna1:

                    st.write("""
                        <div style="text-align: center; color: #333333;">
                            <h1  style="font-size: 14px; margin: 0; padding: 0">Acumulado de chuva das ultimas 24h</h1>
                        </div>
                        """,
                        unsafe_allow_html=True)
                       
                    st.components.v1.html(mapa_html_flu, height=500)
                    
                    url_sib = "https://cth.daee.sp.gov.br/sibh/chuva_agora"
                    st.write(f"""
                        <div style="color: black; line-height: 1;">
                            <p style="text-align: center; font-size: 12px; margin: 0; padding: 0;">Fonte: Chuva agora - <a href="{url_sib}" target="_blank"> SIBH</a></p>
                            <p style="text-align: center; font-size: 12px; margin: 0; padding: 0;"> </p>
                        </div>
                        """,
                    unsafe_allow_html=True) 
                    

                    prefixos_selecionados = st.multiselect(
                        label="Excluir prefixos",
                        options=prefix_list,
                        default=st.session_state.excluir_prefixos,
                        placeholder="Excluir prefixos",
                        label_visibility="collapsed"
                    )

                    # Se mudar a seleção, atualiza o estado e recarrega
                    if set(prefixos_selecionados) != set(st.session_state.excluir_prefixos):
                        st.session_state.excluir_prefixos = prefixos_selecionados
                        st.rerun()
                                        
                with coluna2:

                    st.write("""
                        <div style="text-align: center; color: #333333;">
                            <h1  style="font-size: 14px; margin: 0; padding: 0">Interpolação dos pluviômetros a partir do método IDW</h1>
                        </div>
                        """,
                    unsafe_allow_html=True)
                    
                    # folium_static(mapa, width=500, height=320)
                    # st.markdown(legenda_html, unsafe_allow_html=True)

                    horas = 24
                    data_hora_final = data_hora_inicial - timedelta(hours=horas)

                    sp_border = gpd.read_file('./data/DIV_MUN_SP_2021a.shp').to_crs(epsg=4326)
                    sp_border["geometry"] = sp_border["geometry"].simplify(tolerance=0.01, preserve_topology=True)
                    sp_border_shapefile = "results/sp_border.shp"
                    municipio_arquivo = 'cities_idw'

                    shapefile_path = f'results/acumulado_24_mun_{data_hora_final.strftime("%Y-%m-%d")}.shp'


                    if "interpolar_novamente" not in st.session_state:
                        st.session_state.interpolar_novamente = False


                    if st.session_state.interpolar_novamente or not os.path.exists(shapefile_path):
                        gerar_mapa_chuva_shapefile(sp_border, sp_border_shapefile, municipio_arquivo, prefixos_selecionados)

                    data_stats = gpd.read_file(shapefile_path).to_crs(epsg=4326)
                    data_stats["geometry"] = data_stats["geometry"].simplify(tolerance=0.01, preserve_topology=True)
                    data_stats["mean_precipitation"] = pd.to_numeric(data_stats["mean_preci"], errors='coerce').fillna(0)
                    data_stats.drop(columns=["mean_preci"])

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

                    # folium.TileLayer(
                    #     tiles='https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
                    #     attr=' ',
                    #     name='OpenStreetMap',
                    #     overlay=False,
                    #     control=True, 
                    # ).add_to(mapa)

                    folium.TileLayer(
                        tiles='https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
                        attr='CartoDB',
                        name='CartoDB Light',
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
                    mapa_html_inter = mapa._repr_html_()
                    zoom_css = """
                    <style>
                        body {
                            zoom: 1.5;
                        }
                    </style>
                    """

                    # Insere no <head> do HTML do Folium
                    mapa.get_root().header.add_child(Element(zoom_css))
                    mapa.save("mapa_html_inter.html")

                    mapa.get_root().header.add_child(Element(css_responsivo))
                    st.components.v1.html(mapa_html_inter, height=500)

                    st.write(f"""
                        <div style="color: black; line-height: 1;">
                            <p style="text-align: center; font-size: 12px; margin: 0; padding: 0;">Elaborado pela equipe técnica da Sala de Situação São Paulo (SSSP). Parâmetros: Potência=0.02, Suavização=0.02 e Raio=0.5.</p>
                        </div>
                        """,
                    unsafe_allow_html=True)

                    if st.button("Interpolar novamente"):
                        st.session_state.interpolar_novamente = True
                        st.rerun()
                    
                with colun2:
                       
                    if 'user_input_chuva_slide1' not in st.session_state:
                        st.session_state.user_input_chuva_slide1 = "Clique para editar"
                    
                    user_input = st.text_area("Relatos 24h", value=st.session_state.user_input_chuva_slide1, height=200, label_visibility="collapsed")
                    # user_input = st.text_area("Previsão personalizada", value=st.session_state.user_input_slide8, height=100, label_visibility="collapsed")
                    
            
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

        return user_input



async def slide2():

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
                <h1  style="font-size: 18px;">Dados Pluviometria</h1>
            </div>
            """,
            unsafe_allow_html=True)


        coluna1, coluna2= st.columns([1.0, 0.9])

        prefix_list = st.session_state.excluir_prefixos
        if prefix_list:
            prefix_str = ",".join(f"'{p}'" for p in prefix_list)
            filtro_prefixo = f"AND re.prefix NOT IN ({prefix_str})"
        else:
        # Lista vazia – ignora o filtro
            filtro_prefixo = ""

        if "atualizar_tabela" not in st.session_state:
            st.session_state.atualizar_tabela = False


        if st.session_state.atualizar_tabela:
            refresh_viwe()

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
                        END AS media_historica,
                    re.execution_date
                FROM public.station_rainfall_accum_month re
                    LEFT JOIN cities c ON c.id = re.city_id
                    LEFT JOIN avg_rainfall_cities rc ON rc.cod_ibge::text = c.cod_ibge::text
                WHERE disponibilidade_diaria > 80 AND disponibilidade_mensal > 60::numeric AND ac_diario IS NOT null and c.name!='Município não Existente ou Incorporado por Outro' {filtro_prefixo}
                GROUP BY city_name, media_historica, execution_date
                ORDER BY (max(ac_diario)) DESC LIMIT 10;"""

        tabela_df= execute_query(query_cities)
        ultima_atualizacao = tabela_df['execution_date'].iloc[0]
        tabela_df = tabela_df.drop(columns=['execution_date'], errors='ignore')
        # print(tabela_df)
        tabela_df['media_historica'] = pd.to_numeric(tabela_df['media_historica'], errors='coerce')
        tabela_df['media_historica'] = tabela_df['media_historica'].round(1)
        tabela_df['media_historica'] = tabela_df['media_historica'].apply(lambda x: f'{x:.1f}' if pd.notna(x) else '-')
        tabela_df = tabela_df.rename(columns={'city_name': 'Municípios', 'max_ac_diario': 'Chuva Máximo (mm)', 'ac_diario': 'Chuva Média (mm)', 'ac_mensal':'Acum. média mês (mm)' , 'media_historica':'Histórico mensal (mm)'})

        # query_ugrhis = f"""
        #                 SELECT INITCAP(u.name) as ugrhi_name,
        #                     avg(ac_diario) AS ac_diario
        #                 FROM public.station_rainfall_accum_month sr
        #                     left join stations s on s.id = sr.ugrhi_id
        #                     LEFT JOIN ugrhis u ON u.id = s.id
        #                 WHERE disponibilidade_diaria > 80 AND ac_diario IS NOT null AND u.name != 'FORA DO ESTADO DE SÃO PAULO'
        #                 GROUP BY ugrhi_name
        #                 ORDER BY (ac_diario) DESC;"""
        
        # query_ugrhis = f"""
        #                 SELECT INITCAP(u.name) as ugrhi_name,
        #                     avg(ac_diario) AS ac_diario
        #                 FROM public.station_rainfall_accum_month sr
        #                     left join stations s on s.id = sr.ugrhi_id
        #                     LEFT JOIN ugrhis u ON u.id = s.id
        #                 WHERE disponibilidade_diaria > 80 AND ac_diario IS NOT null AND u.name != 'FORA DO ESTADO DE SÃO PAULO'
        #                 GROUP BY ugrhi_name
        #                 ORDER BY (ac_diario) DESC;"""
        query_ugrhis = f"""
            SELECT INITCAP(u.name) as ugrhi_name, u.cod,
                avg(ac_diario) AS ac_diario,
                avg(ac_mensal) AS ac_mensal,
                avg(CASE
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
                end) AS media_historica
            FROM public.station_rainfall_accum_month sr
                left join stations s on s.id = sr.ugrhi_id
                LEFT JOIN ugrhis u ON u.id = s.id
                LEFT JOIN cities c ON c.id = sr.city_id
                LEFT JOIN avg_rainfall_cities rc ON rc.cod_ibge::text = c.cod_ibge::text
            WHERE disponibilidade_diaria > 80 AND ac_diario IS NOT null AND u.name != 'FORA DO ESTADO DE SÃO PAULO'
            GROUP BY ugrhi_name, u.cod
            ORDER BY u.cod;
        """
        tabela_ugrhis_df= execute_query(query_ugrhis)
        tabela_ugrhis_df['media_historica'] = pd.to_numeric(tabela_ugrhis_df['media_historica'], errors='coerce')
        tabela_ugrhis_df['media_historica'] = tabela_ugrhis_df['media_historica'].round(1)
        tabela_ugrhis_df['media_historica'] = tabela_ugrhis_df['media_historica'].apply(lambda x: f'{x:.1f}' if pd.notna(x) else '-')

        tabela_ugrhis_df = tabela_ugrhis_df.rename(columns={'ugrhi_name': 'Ugrhi', 'ac_diario': 'Chuva Acumulada (mm)', 'ac_mensal':'Acum. mensal (mm)' , 'media_historica':'Histórico mensal (mm)'})
        print(tabela_ugrhis_df)

        # tabela_df = tabela_df.sort_values(by='Chuva Máximo (mm)')

        first_column_name = tabela_df.columns[0]
        with coluna1:

            styled_df = tabela_df.style\
            .format({
                    'Chuva Máximo (mm)': '{:.1f}',
                    'Chuva Média (mm)': '{:.1f}',
                    'Acum. média mês (mm)': '{:.1f}'
                    })\
            .hide(axis="index")\
            .set_caption("Municípios com os maiores acumulados de chuvas observadas nas últimas 24h (mm) (Rede Telemétrica)")\
            .set_table_styles([
                {"selector": "caption", "props": [
                    ("color", "black"),
                    ("font-size", "16px"),
                    ("font-weight", "bold"),
                    ("text-align", "center"),
                    ("padding", "5px"),
                    ("caption-side", "top")
                ]},
                {"selector": "th", "props": [
                    ("font-size", "16px"),
                    ("background-color", "#F0F0F0"),
                    ("color", "#333333"),
                    ("padding", "5px"),
                    ("text-align", "center")
                    ]},
                {"selector": "td", "props": [
                    ("font-size", "16px"),
                    ("height", "7px"),
                    ("color", "#333333"),
                    ("padding", "2px 4px"),
                    ("text-align", "center"),
                    ("width", "100px")
                    # ("border-bottom", "1px solid #E0E0E0")
                    ]},
                {"selector": "tr:hover", "props": [(
                    "background-color", "#FFFF99"),
                    ("cursor", "pointer")
                    ]},
                {"selector": "th.col0", "props": [("width", "150px")]},
                {"selector": "td.col0", "props": [("width", "150px")]},
                {"selector": "th.col1", "props": [("width", "110px")]},
                {"selector": "td.col1", "props": [("width", "110px")]},
                {"selector": "th.col2", "props": [("width", "100px")]},
                {"selector": "td.col2", "props": [("width", "100px")]},
                {"selector": "th.col3", "props": [("width", "110px")]},
                {"selector": "td.col3", "props": [("width", "110px")]},
                {"selector": "th.col4", "props": [("width", "110px")]},
                {"selector": "td.col4", "props": [("width", "110px")]},

            ])\
            .set_properties(**{"background-color": "#F9F9F9", "color": "#333333"})

            st.markdown(styled_df.to_html(), unsafe_allow_html=True)

            html_tabela = styled_df.to_html()

            soup = BeautifulSoup(styled_df.to_html(), 'html.parser')
            caption = soup.find('caption')
            if caption:
                caption.decompose()

            html_sem_titulo = str(soup)

            os.makedirs("imagens", exist_ok=True)
            caminho_imagem = "imagens/tabela_chuva.png"
            if os.path.exists(caminho_imagem):
                os.remove(caminho_imagem)

            hti = Html2Image(
                custom_flags=[
                "--headless=new",
                "--disable-gpu",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--force-device-scale-factor=3"
            ]
            )
            hti.output_path = "imagens"
            chrome_path = localizar_chrome()
            hti.browser_path = chrome_path
            hti.screenshot(html_str=html_sem_titulo, save_as='tabela_chuva.png', size=(700, 500))


            if prefix_list:
                soup = BeautifulSoup(styled_df.to_html(), 'html.parser')
                caption = soup.find('caption')
                if caption:
                    caption.decompose()

                html_sem_titulo = str(soup)

                os.makedirs("imagens", exist_ok=True)
                caminho_imagem = "imagens/tabela_chuva.png"
                if os.path.exists(caminho_imagem):
                    os.remove(caminho_imagem)

                hti = Html2Image(
                    custom_flags=[
                    "--headless=new",
                    "--disable-gpu",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--force-device-scale-factor=3"
                ]
                )
                hti.output_path = "imagens"
                chrome_path = localizar_chrome()
                hti.browser_path = chrome_path
                hti.screenshot(html_str=html_sem_titulo, save_as='tabela_chuva.png', size=(700, 500))


            st.write("""
                    <div class="align-left-center">
                        <div style="color: black; line-height: 1;">
                            <p style="font-size: 14px; margin: 0.5; padding: 0;">  1- Máximo Registrado - Volume máximo (mm) registrado por um posto pluviométrico do município.</p>
                            <p style="font-size: 14px; margin: 0.5; padding: 0;">  2- Média Registrada - Soma do Volume (mm) de todos postos do municípios / n°postos.</p>
                            <p style="font-size: 14px; margin: 0.5; padding: 0;">  3- Acumulado média mês - Soma da média (mm) registrada do primeiro dia do mês até o momento.</p>
                            <p style="font-size: 14px; margin: 0.5; padding: 0;">  4- Histórico mensal - Volume médio mensal calculado a partir da série histórica disponível</p>
                        </div>
                    </div>
                """,
                unsafe_allow_html=True)


            if st.button("Atualizar Tabela"):
                st.session_state.atualizar_tabela = True
                st.rerun()

            st.write(f"""
                    <div class="align-left-center">
                        <div style="color: black; line-height: 1;">
                            <p style="font-size: 10px; margin: 0.5; padding: 0;">  <i>Ultima atualização: {ultima_atualizacao}</i></p>
                        </div>
                    </div>
                """,
                unsafe_allow_html=True)

        tabela_df['Histórico mensal (mm)'] = tabela_df['Histórico mensal (mm)'].replace('-', 0)



        with coluna2:
            for col in ['Chuva Média (mm)', 'Chuva Máximo (mm)', 'Acum. média mês (mm)', 'Histórico mensal (mm)']:
                tabela_df[col] = tabela_df[col].astype(float)


            fig, ax = plt.subplots(figsize=(7, 5))

            n = len(tabela_df)  # Número de municípios
            largura_barra = 0.15  # Largura de cada barra individual
            espacamento = 0.05  # Espaço entre grupos de barras
            indice = np.arange(n)  # Posições no eixo X
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
            # ax.set_xlabel('Municípios', fontsize=8)
            ax.set_ylabel('Precipitação (mm)', fontsize=8)
            ax.set_xticks(indice)
            ax.set_xticklabels(tabela_df['Municípios'], rotation=30, ha='right', fontsize=10)
            ax.grid(axis='y', linestyle=':', alpha=0.3)

            # Ajuste do eixo Y
            max_valor = tabela_df[['Chuva Média (mm)', 'Chuva Máximo (mm)',
                                'Acum. média mês (mm)', 'Histórico mensal (mm)']].max().max()
            ax.set_ylim(0, max_valor * 1.2)
            ax.set_yticks(np.arange(0, max_valor * 1.2 + 0, 25))



            # Legenda fora do gráfico
            ax.legend(
                frameon=True,
                facecolor='#F0F0F0',
                fontsize=7,
                bbox_to_anchor=(0.5, 1.1),  # (posição horizontal, posição vertical)
                loc='upper center',  # Âncora no centro superior
                ncol=4  # Número de colunas para distribuir os itens
            )

            plt.tight_layout()
            st.pyplot(fig)
            ax.set_title("")
            fig.savefig("imagens/grafico_chuva.png", dpi=300, bbox_inches="tight")

        with coluna2:
            for col in ['Chuva Acumulada (mm)', 'Acum. mensal (mm)' ,'Histórico mensal (mm)']:
                tabela_ugrhis_df[col] = tabela_ugrhis_df[col].astype(float)

            fig, ax = plt.subplots(figsize=(8, 6))
            # Definindo as posições das barras
            n = len(tabela_ugrhis_df)
            indice = np.arange(n)  # Posições no eixo X (0, 1, 2, ...)

            # Largura das barras
            largura_barra = 0.28  # Largura de cada barra individual
            espacamento = 0.01  # Espaço entre grupos de barras
            indice = np.arange(n)  # Posições no eixo X
            offset = np.array([-1, 0, 1]) * (largura_barra + espacamento/2)

            cores = ['#2196F3', '#FF5722', '#FFC107']

            # Plotagem das barras
            for i, (coluna, cor) in enumerate(zip(
                ['Chuva Acumulada (mm)', 'Acum. mensal (mm)' ,'Histórico mensal (mm)'],
                cores
            )):
                ax.bar(
                    indice + offset[i],
                    tabela_ugrhis_df[coluna],
                    largura_barra,
                    color=cor,
                    alpha=0.8,
                    label=coluna
                )


            # Ajuste do eixo Y
            max_valor = tabela_ugrhis_df[
                ['Chuva Acumulada (mm)', 'Acum. mensal (mm)', 'Histórico mensal (mm)']
            ].max().max()
            ax.set_ylim(0, max_valor * 1.2)
            ax.set_yticks(np.arange(0, max_valor * 1.2 + 0, 25))


            # Legenda fora do gráfico
            ax.legend(
                frameon=True,
                facecolor='#F0F0F0',
                fontsize=7,
                bbox_to_anchor=(0.5, 1.1),  # (posição horizontal, posição vertical)
                loc='upper center',  # Âncora no centro superior
                ncol=4  # Número de colunas para distribuir os itens
            )

            ax.set_title('Chuva média acumulada por UGRHI', fontsize=10, pad=30)             # Título do gráfico
            ax.set_xticks(indice)                           # Define os ticks no eixo X
            ax.set_xticklabels(tabela_ugrhis_df['Ugrhi'], fontsize=10)     # Nomes das UGRHIs nos ticks
            ax.set_ylabel('Precipitação (mm)', fontsize=8)

            # max_valor = tabela_ugrhis_df['ac_diario'].max()

            # ax.set_yticks(np.arange(0, max_valor * 1.2 + 0, 25))


            # Rotaciona os rótulos do eixo X para melhor visualização (opcional)
            plt.xticks(rotation=30, ha='right')

            plt.tight_layout()
            st.pyplot(fig)
            ax.set_title("")
            fig.savefig("imagens/grafico_chuva2.png", dpi=300, bbox_inches="tight")

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

        return None


async def slide3():
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
                <h1  style="font-size: 18px;">Acumulados dos Radares</h1>
            </div>
            """,
            unsafe_allow_html=True)

        coluna1, coluna2= st.columns([1.2, 0.8])  

        # IPMET
        data_inicial = datetime.today()
        data_str = data_inicial.strftime('%Y-%m-%d')

        image_path = f'results/imagem_ipmet_{data_str}.png'

        if os.path.exists(image_path):
            img_ipmet = Image.open(image_path)
            
        else:
            img_ipmet, url_ipmet = capturar_ipmet()

        url_ipmet = "https://www.ipmetradar.com.br/2mobileGis.php"

        legenda_ipmet = Image.open("escala_acum.png")

        with coluna1:
            st.write("""
            <div style="text-align: center; color: #333333;">
                <h1  style="font-size: 14px; margin: 0; padding: 0">Acumulado das 24h (mm) - Radar Ipmet</h1>
            </div>
            """,
            unsafe_allow_html=True)
            st.image(img_ipmet, caption="", use_container_width=True)

            cl1, cl2, cl3= st.columns([0.8, 1.0, 0.8])  
            with cl2:
                st.image(legenda_ipmet, caption="", use_container_width=True)

            st.write(f"""
                    <div style="color: black; line-height: 1;">
                        <p style="text-align: center; font-size: 12px; margin: 0; padding: 0;">Produzido pelo Ipmet. Disponível em: <a href="{url_ipmet}" target="_blank"> IPMET</a></p>
                    </div>
                """,
            unsafe_allow_html=True)

            if 'user_input' not in st.session_state:
                st.session_state.user_input = "Clique para editar"
            
            user_input = st.text_area("Análise", value=st.session_state.user_input, height=100)
            
            if user_input != st.session_state.user_input:
                st.session_state.user_input = user_input


        # SAISP

        image_path = f'results/imagem_saisp_{data_str}.png'

        if os.path.exists(image_path):
            img_saisp = Image.open(image_path)
            
        else:
            img_saisp, url_saisp = capturar_saisp()

        url_saisp = "https://www.saisp.br/estaticos/sitenovo/home.html"

        # img_saisp = Image.open("results/imagem_saisp.png")
        # img_saisp, url_saisp = capturar_saisp()
        with coluna2:
            st.write("""
            <div style="text-align: center; color: #333333;">
                <h1  style="font-size: 14px; margin: 0; padding: 0">Acumulado das 24h (mm) - Radar SP Águas</h1>
            </div>
            """,
            unsafe_allow_html=True)
            st.image(img_saisp, use_container_width=True)
            st.image("imagens/Imagem1.jpg", use_container_width=True)
            st.write(f"""
                    <div style="color: black; line-height: 1;">
                        <p style="text-align: center; font-size: 12px; margin: 0; padding: 0;">Produzido pelo Radar 600S-Selex, Banda S, 850 KW, Doppler, Dupla Polarização. Disponível em: <a href="{url_saisp}" target="_blank"> SAISP</a></p>
                    </div>
                """,
            unsafe_allow_html=True)

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
        return user_input

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
                <h1  style="font-size: 14px;">Mapa de precipitação pluviométrica das últimas 24 horas </h1>
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
                <h1  style="font-size: 18px;">Dados Fluviometria</h1>
            </div>
            """,
            unsafe_allow_html=True)


        c1, c2, c3 = st.columns([0.1, 1.2, 0.2])

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
        
        query_view = f"select * from estados_estacoes_24h;"
        df_extravasation= execute_query(query)

        prefix_list = sorted(df_extravasation['prefix'].dropna().unique().tolist())

        if 'excluir_prefixos_fluvio' not in st.session_state:
            st.session_state.excluir_prefixos_fluvio = []


        df_extravasation['value'] = pd.to_numeric(df_extravasation['value'], errors='coerce')
        df_extravasation['latitude'] = pd.to_numeric(df_extravasation['latitude'], errors='coerce')
        df_extravasation['longitude'] = pd.to_numeric(df_extravasation['longitude'], errors='coerce')
        df_extravasation['station_prefix_id'] = df_extravasation['station_prefix_id'].astype(str)
        df_extravasation = df_extravasation.sort_values(by="value", ascending=True)

        if st.session_state.excluir_prefixos_fluvio:
            df_extravasation = df_extravasation[~df_extravasation['prefix'].isin(st.session_state.excluir_prefixos_fluvio)]

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

        estados = ['Extravasamento','Emergência', 'Alerta', 'Atenção', 'Normal']

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
                if percentages.get(estado, 0) == 1:
                    partes_porcentagens.append(f"{percentages.get(estado, 0)} posto em nível de {estado}")
                elif percentages.get(estado, 0) > 1:
                    if estado != 'Normal':
                        partes_porcentagens.append(f"{percentages.get(estado, 0)} postos em nível de {estado}")
                    else:
                        partes_porcentagens.append(f"{percentages.get(estado, 0)} postos em nível {estado}")
                else:
                    estado_sem_registro.append(estado)

        # Construindo a legenda
        legenda = "De acordo com os registros das redes telemétricas públicas do Estado de São Paulo nas últimas 24h foram registrados "

        # Primeiro Extravasamento/Emergência
        if dados_criticos:
            if len(dados_criticos) == 1:
                legenda += f" níveis em {dados_criticos[0]}, "
            else:
                legenda += f" níveis de {dados_criticos[0]} e {dados_criticos[1]}, "

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
            
            legenda += f" Não ocorreram Extravasamentos durante o período analisado."
        


        mapa = folium.Map(
            location=[-22.7832, -48.4430],  # Centralizar no meio dos pontos
            zoom_start=6.0,
            tiles=None,
            control_scale=False, 
            zoomControl=False
        )

        # folium.TileLayer(
        #     tiles='https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
        #     attr=' ',
        #     name='OpenStreetMap',
        #     overlay=False,
        #     control=True
        # ).add_to(mapa)

        folium.TileLayer(
            tiles='https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
            attr='CartoDB',
            name='CartoDB Light',
        ).add_to(mapa)

        mapa.options['attributionControl'] = False

        shapefile_path = "data/limiteestadualsp.shp"
        gdf = gpd.read_file(shapefile_path)
        gdf["geometry"] = gdf["geometry"].simplify(tolerance=0.01, preserve_topology=True)

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
            station_name = row['station_name']
            prefix = row['prefix']

            valor_inteiro = int(valor)

            if valor_inteiro>0:
                # Criar um popup com o valor
                popup_texto = f"Valor: {valor}<br>Station: {station_name}<br>Prefix: {prefix}"
                popup = Popup(popup_texto, max_width=300) 

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
        
        mapa.save("mapa_slide5.html")

        c1, c2, c3 = st.columns([0.1, 1.2, 0.1])

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
            
            prefixos_selecionados = st.multiselect(
                label="Exlcuir prefixos",
                options=prefix_list,
                default=st.session_state.excluir_prefixos_fluvio,
                placeholder="Excluir prefixos",
                label_visibility="collapsed"
            )

            # Se mudar a seleção, atualiza o estado e recarrega
            # if set(prefixos_selecionados) != set(st.session_state.excluir_prefixos_fluvio):
            #     st.session_state.excluir_prefixos_fluvio = prefixos_selecionados
            #     st.rerun()
            st.session_state.excluir_prefixos_fluvio = prefixos_selecionados

        colun1, colun2, colun3 = st.columns([0.2, 1.2, 0.2])
            
        with colun2:    
            if 'user_input_slide5' not in st.session_state:
                st.session_state.user_input_slide5 = legenda  # sem f-string desnecessária

            user_input = st.text_area("Análise das redes Telemétrica", height=100, key="user_input_slide5")


        with colun3:
            csv = df_max_values.to_csv(index=False).encode('utf-8')
                
            st.download_button(
                label="⎙",
                data=csv,
                file_name='fluviometria_chuva.csv',
                mime='text/csv'
                )


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

            all_extravasamento = []
            for i, station_prefix_id in enumerate(prefix_id, start=1):  # Iterando sobre os IDs já conhecidos
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
                        <h1  style="font-size: 18px;">Gráfico do Extravasamento</h1>
                    </div>
                    """,
                    unsafe_allow_html=True)


                html_perc_blocks = f"""
                    <div style="display: flex; justify-content: center; gap: 16px; flex-wrap: wrap; padding: 20px;">
                        <div style="background-color:#da070f; padding: 12px; border-radius: 8px; width: 180px; height: 80px; display: flex; flex-direction: column; justify-content: center; align-items: center;"">
                            <div style="color: white; font-size: 18px;"><strong>Extravasamento</strong></div>
                            <div style="color: white; font-size: 16px;">{percentages['Extravasamento']:.2f}%</div>
                        </div>
                        <div style="background-color:#8435b7; padding: 12px; border-radius: 8px; width: 180px; height: 80px; display: flex; flex-direction: column; justify-content: center; align-items: center;"">
                            <div style="color: white; font-size: 18px;"><strong>Emergência</strong></div>
                            <div style="color: white; font-size: 16px;">{percentages['Emergência']:.2f}%</div>
                        </div>
                        <div style="background-color:#f95108; padding: 12px; border-radius: 8px; width: 180px; height: 80px; display: flex; flex-direction: column; justify-content: center; align-items: center;"">
                            <div style="color: white; font-size: 18px;"><strong>Alerta</strong></div>
                            <div style="color: white; font-size: 16px;">{percentages['Alerta']:.2f}%</div>
                        </div>
                        <div style="background-color:#f8d202; padding: 12px; border-radius: 8px; width: 180px; height: 80px; display: flex; flex-direction: column; justify-content: center; align-items: center;"">
                            <div style="color: white; font-size: 18px;"><strong>Atenção</strong></div>
                            <div style="color: white; font-size: 16px;">{percentages['Atenção']:.2f}%</div>
                        </div>
                        <div style="background-color:#268b12; padding: 12px; border-radius: 8px; width: 180px; height: 80px; display: flex; flex-direction: column; justify-content: center; align-items: center;"">
                            <div style="color: white; font-size: 18px;"><strong>Normal</strong></div>
                            <div style="color: white; font-size: 16px;">{percentages['Normal']:.2f}%</div>
                        </div>
                    </div>
                    """
                st.markdown(html_perc_blocks, unsafe_allow_html=True)

                caminho_imagem = f"imagens/barras_percentuais{i}.png"
                if os.path.exists(caminho_imagem):
                    os.remove(caminho_imagem)

                hti = Html2Image(
                    custom_flags=[
                    "--headless=new",
                    "--disable-gpu",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--force-device-scale-factor=3"
                ]
                )
                hti.output_path = "imagens"
                chrome_path = localizar_chrome()
                hti.browser_path = chrome_path

                hti.screenshot(html_str=html_perc_blocks, save_as=f'barras_percentuais{i}.png', size=(1200, 300))

                fig = go.Figure()
                df_filtered['current_data'] = df_filtered['current_data'] - pd.Timedelta(hours=3)
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

                html_str = fig.to_html(full_html=False, include_plotlyjs='cdn')

                caminho_imagem_ploty = f"imagens/grafico_plotly{i}.png"
                if os.path.exists(caminho_imagem_ploty):
                    os.remove(caminho_imagem_ploty)

                hti = Html2Image(
                    custom_flags=[
                    "--headless=new",
                    "--disable-gpu",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--force-device-scale-factor=3"
                ]
                )
                hti.output_path = "imagens"
                chrome_path = localizar_chrome()
                hti.browser_path = chrome_path

                hti.screenshot(html_str=html_str, save_as=f'grafico_plotly{i}.png', size=(1100, 600))

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

                html_str = styled_df.to_html()
                os.makedirs("imagens", exist_ok=True)
                caminho_imagem = f"imagens/tabela_resumo{i}.png"
                if os.path.exists(caminho_imagem):
                    os.remove(caminho_imagem)
                hti = Html2Image(
                        custom_flags=[
                        "--headless=new",
                        "--disable-gpu",
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--force-device-scale-factor=3"
                    ]
                    )
                hti.output_path = "imagens"  # ou outro diretório
                chrome_path = localizar_chrome()
                hti.browser_path = chrome_path
                hti.screenshot(html_str=html_str, save_as=f'tabela_resumo{i}.png', size=(1200, 300))
                st.markdown(styled_df.to_html(), unsafe_allow_html=True)

                # st.table(styled_df)
                # st.dataframe(styled_df, use_container_width=True)

                all_extravasamento.append({
                    "numero": i,  # <--- numerando aqui
                    "station_id": id_station,
                    "station_name": name_station,
                    "cards_image":f'barras_percentuais{i}.png',
                    "grafico_path": f'grafico_plotly{i}.png',
                    "tabela_resumo": f"tabela_resumo{i}.png",
                    "percentuais": percentages,
                    "resumo": summary_data,
                    # ... outros dados
                })

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

            return user_input, all_extravasamento
            
        else:
            all_extravasamento = None
            return user_input, all_extravasamento
            
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
                <h1  style="font-size: 18px;">Sistema Produtores da RMSP</h1>
            </div>
            """,
            unsafe_allow_html=True)


        coluna1, coluna2, coluna3 = st.columns([0.2, 1.5, 0.2])

        data_atual = datetime.today()
        data_ano_anterior = datetime.today() - timedelta(days=365)
        data_7dias = datetime.today() - timedelta(days=7)
        data_14dias = datetime.today() - timedelta(days=14)
        data_21dias = datetime.today() - timedelta(days=21)

        data_atual_str = data_atual.strftime('%Y-%m-%d')
        data_ano_anterior_str = data_ano_anterior.strftime('%Y-%m-%d')

        with coluna2:
            
            url = 'https://cth.daee.sp.gov.br/ssdsp/'

            data_inicial = datetime.today()
            data_str = data_inicial.strftime('%Y-%m-%d')

            image_path = f'results/imagem_rmsp.png'

            # if os.path.exists(image_path):
            #     imagem_recortada = Image.open(image_path)
                
            # else:
            #     print("Entrou else rmsp")
            imagem = capturar_tela(url)
            imagem_recortada = imagem.crop((90, 945, 1200, 1650))#esquerda, cima, direita, baixo
            output_rmsp = os.path.join("results", f"imagem_rmsp.png")
            imagem_recortada.save(output_rmsp) 
            imagem_recortada = Image.open(image_path)

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

        json_sistemas = 'results/sabesp_sistemas.json'
        sistemas_esperados = {"Cantareira", "Alto Tietê", "Guarapiranga", "Cotia", "Rio Grande", "Rio Claro", "São Lourenço", 'SIM'}

        if "atualizar_cantareira" not in st.session_state:
            st.session_state.atualizar_cantareira = False


        if st.session_state.atualizar_cantareira:
            get_sabesp_api_resumo(data_atual_str, data_ano_anterior_str)

        if os.path.exists(json_sistemas):
            merged_data_sistemas = pd.read_json(json_sistemas)

            # Checa se todos os sistemas esperados estão presentes no JSON
            sistemas_presentes = set(merged_data_sistemas["Sistema"].unique())

            # Verifica se para todos os sistemas esperados há pelo menos uma linha com a data_atual_str
            data_faltando = False
            for sistema in sistemas_esperados:
                df_sis = merged_data_sistemas[merged_data_sistemas["Sistema"] == sistema]
                if data_atual_str not in df_sis["Data"].values:
                    data_faltando = True
                    break

            # Se faltar qualquer sistema com a data atual, ou faltar sistema no geral → refaz
            if data_faltando or not sistemas_esperados.issubset(sistemas_presentes):
                get_sabesp_api_resumo(data_atual_str, data_ano_anterior_str)
                merged_data_sistemas = pd.read_json(json_sistemas)
                merged_data_sistemas = merged_data_sistemas.drop(columns=["Data"])
            else:
                merged_data_sistemas = merged_data_sistemas.drop(columns=["Data"])
        else:
            get_sabesp_api_resumo(data_atual_str, data_ano_anterior_str)
            merged_data_sistemas = pd.read_json(json_sistemas)
            merged_data_sistemas = merged_data_sistemas.drop(columns=["Data"])


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
                <h1  style="font-size: 18px;">Sistema Produtores da RMSP</h1>
            </div>
            """,
            unsafe_allow_html=True)

        st.write(" ") 
        st.write(" ")
        st.write(" ")
        st.write(" ")

        colun1, colun2= st.columns([1.0, 1.0])
        with colun1:
            for col in ['Volume Atual (%)', 'Volume Ano Anterior (%)']:
                merged_data_sistemas[col] = merged_data_sistemas[col].astype(float)

                fig, ax = plt.subplots(figsize=(7, 5)) 

                # Configurações das barras
                n = len(merged_data_sistemas) 
                largura_barra = 0.44 
                espacamento = 0.05
                indice = np.arange(n) 

                # Offset calculado corretamente
                offset = np.array([-0.5, 0.5]) * (largura_barra + espacamento/2)
                cores = ['#83c4d6', '#5169af']

                # Ajuste do eixo Y
                max_valor = merged_data_sistemas[['Volume Atual (%)', 'Volume Ano Anterior (%)']].max().max()
                
                ax.set_ylim(0, max_valor * 1.2)

                # Plotagem das barras
                for i, (coluna, cor) in enumerate(zip(
                    ['Volume Atual (%)', 'Volume Ano Anterior (%)'],
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
                            f'{y:.2f}',           # Número inteiro com símbolo de porcentagem
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
            ax.set_title("")
            fig.savefig("imagens/grafico_rmsp.png", dpi=300, bbox_inches="tight")

        with colun2: 
            styled_df = merged_data_sistemas.style\
            .format({
                    'Volume Atual (%)': '{:.2f}', 
                    'Volume Ano Anterior (%)': '{:.2f}', 
                    'Diferença Vol. Anual (%)': '{:.2f}'
                })\
            .hide(axis="index")\
            .set_caption("Volume dos Sistemas Produtores (Sabesp)")\
            .set_table_styles([
                {"selector": "caption", "props": [
                    ("color", "black"),
                    ("font-size", "14px"),
                    ("font-weight", "bold"),
                    ("text-align", "center"),
                    ("padding", "5px"),
                    ("caption-side", "top") 
                ]},
                {"selector": "th", "props": [ #cabeçalho
                    ("font-size", "14px"),
                    ("height", "12px"), 
                    ("background-color", "#f0f0f0"),
                    ("color", "#333333"),
                    ("padding", "5px"),
                    ("text-align", "center")
                    ]},
                {"selector": "td", "props": [
                    ("font-size", "14px"),
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
            
            html_tabela = styled_df.to_html()

            soup = BeautifulSoup(html_tabela, 'html.parser')
            caption = soup.find('caption')
            if caption:
                caption.decompose()

            html_sem_titulo = str(soup)
            os.makedirs("imagens", exist_ok=True)
            caminho_imagem = "imagens/tabela_rmsp.png"
            if os.path.exists(caminho_imagem):
                os.remove(caminho_imagem)
            hti = Html2Image(
                    custom_flags=[
                    "--headless=new",
                    "--disable-gpu",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--force-device-scale-factor=3"
                ]
                )
            hti.output_path = "imagens"  # ou outro diretório
            chrome_path = localizar_chrome()
            hti.browser_path = chrome_path
            hti.screenshot(html_str=html_sem_titulo, save_as=f'tabela_rmsp.png', size=(800, 600))

            if st.button("Atualizar"):
                        st.session_state.atualizar_cantareira = True
                        st.rerun()


        min_dif_filter = merged_data_sistemas[merged_data_sistemas["Diferença Vol. Anual (%)"] == merged_data_sistemas["Diferença Vol. Anual (%)"].min()].iloc[0]
        max_dif_filter = merged_data_sistemas[merged_data_sistemas["Diferença Vol. Anual (%)"] == merged_data_sistemas["Diferença Vol. Anual (%)"].max()].iloc[0]

        # Acesse o valor escalar com .iloc[0]
        legenda = ""

        # Verifica se existe valor negativo
        if min_dif_filter["Diferença Vol. Anual (%)"] < 0:
            legenda += (
                f"O sistema produtor da Rede Metropolitana de São Paulo (RMSP) {min_dif_filter['Sistema']} "
                f"está a {min_dif_filter['Diferença Vol. Anual (%)']:.2f}% do volume útil em comparação com o mesmo mês no ano anterior, a maior diferença negativa em comparação com os demais sistemas."
                f" Atualmente o seu volume útil está em {min_dif_filter['Volume Atual (%)']:.2f}% e no ano anterior estava com {min_dif_filter['Volume Ano Anterior (%)']:.2f}%."
            )

        # Verifica se existe valor positivo
        if max_dif_filter["Diferença Vol. Anual (%)"] > 0:
            frase_inicial = "Já o sistema" if legenda else "O sistema produtor da Rede Metropolitana de São Paulo (RMSP)"
            legenda += (
                f" {frase_inicial} {max_dif_filter['Sistema']} "
                f"apresentou a maior diferença positiva de {max_dif_filter['Diferença Vol. Anual (%)']:.2f}% em comparação com o mesmo mês no ano anterior, "
                f"hoje apresenta o volume atual de {max_dif_filter['Volume Atual (%)']:.2f}% e no ano anterior estava com {max_dif_filter['Volume Ano Anterior (%)']:.2f}%."
            )


        if 'user_input_slide6' not in st.session_state:
            st.session_state.user_input_slide6 = legenda
        
        user_input = st.text_area("Análise dos Sistemas Produtores", height=120, key="user_input_slide6")
        
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

        return user_input
        

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
                <h1  style="font-size: 18px;">Acumulados das Últimas 72h e Limiares Críticos do PPDC dos Municípios do Estado de São Paulo</h1>
            </div>
            """,
            unsafe_allow_html=True) 
        

        coluna1, coluna2 = st.columns([1.5, 0.6])
        
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
        gdf["geometry"] = gdf["geometry"].simplify(tolerance=0.01, preserve_topology=True)

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

        # folium.TileLayer(
        #     tiles='https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
        #     attr=' ',
        #     name='OpenStreetMap',
        #     overlay=False,
        #     control=True, 
        # ).add_to(mapa)

        folium.TileLayer(
            tiles='https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
            attr='CartoDB',
            name='CartoDB Light',
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
        <div style="position: fixed; z-index:999999; bottom: 170px; left: 50%; transform: translateX(-50%); background: white; padding: 2px; border-radius: 5px; box-shadow: 0 0 3px rgba(0,0,0,0.3); display: flex; align-items: center; justify-content: center;">
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

            mapa.save("mapa_html_ppdc.html")

            st.components.v1.html(mapa_html, width=860, height=350)
            url = 'https://cth.daee.sp.gov.br/sibh/chuva_agora'
            st.markdown(f'<p style="text-align: center; font-size: 12px">Elaborado pela equipe do SP Águas. Fonte: <a href="{url}" target="_blank">SIBH</a> </a></p>', unsafe_allow_html=True)
            st.write(" ")
            
        with coluna2:

            legenda = '"O PPDC - Plano Preventivo de Defesa Civil específico para escorregamentos nas encostas da Serra do Mar no Estado de São Paulo (Decreto Estadual nº 30,860 de 04/12/1989, redefinido pelo Decreto Estadual nº42,565 de 01/12/1997) tem por objetivo principal evitar a ocorrência de mortes, com a remoção preventiva e temporária da população que ocupa as áreas de risco, antes que os escorregamentos atinjam suas moradias"'
            if 'user_input_slide7' not in st.session_state:
                st.session_state.user_input_slide7 = legenda 

            user_input = st.text_area("Plano Preventivo de Defesa Civil específico para escorregamentos", height=340, key="user_input_slide7")


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

        html_tabela = styled_df.to_html()

        soup = BeautifulSoup(html_tabela, 'html.parser')
        caption = soup.find('caption')
        if caption:
            caption.decompose()

        html_sem_titulo = str(soup)

        os.makedirs("imagens", exist_ok=True)
        caminho_imagem = "imagens/tabela_ppdc.png"
        if os.path.exists(caminho_imagem):
            os.remove(caminho_imagem)

        hti = Html2Image(
                custom_flags=[
                "--headless=new",
                "--disable-gpu",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--force-device-scale-factor=3"
            ]
            )
        hti.output_path = "imagens"  # ou outro diretório
        chrome_path = localizar_chrome()
        hti.browser_path = chrome_path
        hti.screenshot(html_str=html_sem_titulo, save_as=f'tabela_ppdc.png', size=(800, 600))

        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")
        st.write(" ")

        return user_input


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
                <h1  style="font-size: 18px;">Previsão do Tempo</h1>
            </div>
            """,
            unsafe_allow_html=True) 
        
        coluna1, coluna2 = st.columns([1.0, 1.0])

        data_inicial = datetime.today()
        data_inicial_str = data_inicial.strftime('%Y-%m-%d')

        url = f"https://apivime.inmet.gov.br/COSMO7/SE/prec7dias/{data_inicial_str}H00:00"
        url_imgs = 'https://imgs.somarmeteorologia.com.br/v3/figuras/ncl/somarmet/SE_prec_2.jpg'
        print(url)
        try:
            response = requests.get(url, verify=False, timeout=10)

            if response.status_code == 200:
                data = response.json()
                image_data = next((item for item in data if item["validade"] == 36), None)

                if image_data:
                    # Extrai e decodifica a string base64 da imagem
                    img_base64 = image_data["base64"].split("base64,")[-1]
                    img_data = base64.b64decode(img_base64)
                    image = Image.open(BytesIO(img_data))
                else:
                    # Se não achou no JSON, pega direto a imagem alternativa
                    print("Imagem não encontrada no JSON. Usando imagem alternativa.")
                    image = Image.open(BytesIO(requests.get(url_imgs).content))
            else:
                # Se a API não respondeu com sucesso, pega a imagem alternativa
                print("API não disponível. Usando imagem alternativa.")
                image = Image.open(BytesIO(requests.get(url_imgs).content))
                url = url_imgs

        except Exception as e:
            # Se deu erro na requisição, usa a imagem alternativa
            print(f"Erro ao buscar a imagem da API: {e}. Usando imagem alternativa.")
            image = Image.open(BytesIO(requests.get(url_imgs, verify=False).content))



        with coluna1:
            st.image(image, caption="", use_container_width=True)
            fonte = "https://vime.inmet.gov.br/"
            st.write(f"""
                    <div style="color: black;">
                        <p style="font-size: 12px; margin: 0.5; text-align: center";">Fonte: <a href="{fonte}" target="_blank">Inmet</a></p>  
                    </div>
                """,
            unsafe_allow_html=True)


        with coluna2:
            data = datetime.today()
            data_atual_str = data.strftime('%d-%m-%Y').replace('-', '/')

            st.write(f"""
                    <div style="color: black; line-height: 1;">
                        <p style="font-size: 14px; margin: 0.5; text-align: center";"><strong>Previsão do Tempo para os dias seguintes:</strong></p>
                    </div>
                """,
            unsafe_allow_html=True) 

            legenda = "Clique para editar"
            if 'user_input_slide8' not in st.session_state:
                st.session_state.user_input_slide8 = legenda
            
            user_input = st.text_area("Previsão personalizada", value=st.session_state.user_input_slide8, height=100, label_visibility="collapsed")

        return image, user_input, url
            

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
                <h1  style="font-size: 18px;">Pentada</h1>
            </div>
            """,
            unsafe_allow_html=True) 
        
        coluna1, coluna2 = st.columns([1.0, 1.0])

        data_inicial = datetime.today()
        data_inicial_str = data_inicial.strftime('%Y-%m-%d')

        url = f"https://apivime.inmet.gov.br/COSMO7/SE/prec7dias/{data_inicial_str}H00:00"
        url_imgs = 'https://imgs.somarmeteorologia.com.br/v3/figuras/ncl/somarmet/SE_prec_6.jpg'
        print(url)
        try:
            response = requests.get(url, verify=False, timeout=10)

            if response.status_code == 200:
                data = response.json()
                image_data = next((item for item in data if item["validade"] == 120), None)

                if image_data:
                    # Extrai e decodifica a string base64 da imagem
                    img_base64 = image_data["base64"].split("base64,")[-1]
                    img_data = base64.b64decode(img_base64)
                    image = Image.open(BytesIO(img_data))
                else:
                    # Se não achou no JSON, pega direto a imagem alternativa
                    print("Imagem não encontrada no JSON. Usando imagem alternativa.")
                    image = Image.open(BytesIO(requests.get(url_imgs).content))
            else:
                # Se a API não respondeu com sucesso, pega a imagem alternativa
                print("API não disponível. Usando imagem alternativa.")
                image = Image.open(BytesIO(requests.get(url_imgs).content))
                url = url_imgs

        except Exception as e:
            # Se deu erro na requisição, usa a imagem alternativa
            print(f"Erro ao buscar a imagem da API: {e}. Usando imagem alternativa.")
            image = Image.open(BytesIO(requests.get(url_imgs, verify=False).content))

        with coluna1:

            st.image(image, caption="", use_container_width=True)
            fonte = "https://vime.inmet.gov.br/"
            st.write(f"""
                    <div style="color: black;">
                        <p style="font-size: 12px; margin: 0.5; text-align: center";">Fonte: <a href="{fonte}" target="_blank">Inmet</a></p>  
                    </div>
                """,
            unsafe_allow_html=True)


        with coluna2:
            data = datetime.today()
            data_atual_str = data.strftime('%d-%m-%Y').replace('-', '/')

            st.write(f"""
                    <div style="color: black; line-height: 1;">
                        <p style="font-size: 12px; margin: 0.5; text-align: center";"><strong>Previsão do Tempo para os dias seguintes:</strong></p>  
                    </div>
                """,
            unsafe_allow_html=True) 

            if 'user_input' not in st.session_state:
                st.session_state.user_input = "Clique para editar"
            
            user_input = st.text_area("", value=st.session_state.user_input, height=100)
            
            if user_input != st.session_state.user_input:
                st.session_state.user_input = user_input
        
        return image, user_input, url

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
                <h1  style="font-size: 18px;">Dados Fluviometria - Estiagem</h1>
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
                df_seca = df_seca[df_seca['net_group']!='piscinao_daee']

                df_piscinao = df_seca[df_seca['net_group']=='piscinao_daee']

                
                mapa = folium.Map(
                    location=[-22.7832, -48.4430],  # Centralizar no meio dos pontos
                    zoom_start=6.0,
                    tiles=None,
                    control_scale=False, 
                    zoomControl=False
                )

                # folium.TileLayer(
                #     tiles='https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
                #     attr=' ',
                #     name='OpenStreetMap',
                #     overlay=False,
                #     control=True
                # ).add_to(mapa)

                folium.TileLayer(
                    tiles='https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
                    attr='CartoDB',
                    name='CartoDB Light',
                ).add_to(mapa)

                mapa.options['attributionControl'] = False

                shapefile_path = "data/limiteestadualsp.shp"
                gdf = gpd.read_file(shapefile_path)
                gdf["geometry"] = gdf["geometry"].simplify(tolerance=0.01, preserve_topology=True)

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

                # Adicionar marcadores para cada ponto
                for index, row in df_seca.iterrows():
                    lat = row['latitude']
                    lon = row['longitude']
                    valor = row['value']
                    state = row['current_state']
                    station_name = row['station_name']
                    prefix = row['prefix']

                    valor_inteiro = int(valor)
                    
                    
                    valor_inteiro = int(valor)

                    if valor_inteiro>0:
                        # Criar um popup com o valor
                        popup_texto = f"Valor: {valor}<br>Station: {station_name}<br>Prefix: {prefix}"
                        popup = Popup(popup_texto, max_width=300) 

                        if state == 'Atenção':
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
                <div style="position: fixed; z-index:999999; bottom: 18px; left: 50%; transform: translateX(-50%); background: white; padding: 1px; border-radius: 5px; display: flex; align-items: center; justify-content: center;">
                    <div style="display: flex; align-items: center; margin-right: 5px;">
                        <div style="width: 60px; height: 15px; background-color: #f74f78; display: flex; align-items: center; justify-content: center; color: white; font-size: 8px; border-radius: 3px;">
                            <span> Emergência</span>
                        </div>   
                    </div>
                    <div style="display: flex; align-items: center; margin-right: 5px;">
                        <div style="width: 60px; height: 15px; background-color: #bda501; display: flex; align-items: center; justify-content: center; color: white; font-size: 8px; border-radius: 3px;">
                            <span> Atenção</span>
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
                mapa.save("mapa_slide5_seca.html")

                estados = ['Emergencia', 'Atenção','Normal']

                percentages = {
                    'Atenção': len(df_seca[df_seca['current_state']=='Atenção']),
                    'Normal': len(df_seca[df_seca['current_state']=='Normal'])
                }

                # Separar extravasamento/emergência e outros
                dados_criticos = []  # Para Extravasamento e Emergência
                partes_porcentagens = []
                estado_sem_registro = []

                for estado in estados:
                    if estado in df_seca['current_state'].values and estado in ['Emergencia']:
                        postos = df_seca[df_seca['current_state'] == estado]['station_name'].to_list()

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
                            if estado == 'Normal':
                                partes_porcentagens.append(f"{percentages.get(estado, 0)} postos em nível {estado}")
                            else:
                                partes_porcentagens.append(f"{percentages.get(estado, 0)} postos em nível de {estado}")
                        else:
                            estado_sem_registro.append(estado)


                # Construindo a legenda
                legenda = "De acordo com as redes telemétricas públicas do Estado de São Paulo foram registrados "

                # Primeiro Extravasamento/Emergência
                if dados_criticos:
                    if len(dados_criticos) == 1:
                        legenda += f" níveis em {dados_criticos[0]}, "
                    else:
                        legenda += f" níveis de {dados_criticos[0]} e {dados_criticos[1]}, "

                if partes_porcentagens:
                    if len(partes_porcentagens) == 1:
                        porcentagens_str = partes_porcentagens[0]
                    else:
                        porcentagens_str = ', '.join(partes_porcentagens[:-1]) + ' e ' + partes_porcentagens[-1]
                    
                    legenda += porcentagens_str + "."
                else:
                    legenda += "."

                c1, c2, c3 = st.columns([0.1, 1.2, 0.1])

                with c2:
                    # folium_static(mapa, width=600, height=400)
                    st.components.v1.html(mapa_html, width=1000, height=580)
                
                if 'user_input_slide5_seca' not in st.session_state:
                        st.session_state.user_input_slide5_seca = legenda

                
                # No local onde você quer exibir o text_area
                colun1, colun2, colun3 = st.columns([0.2, 1.2, 0.2])
                with colun2:    
                    url_sib = "https://cth.daee.sp.gov.br/sibh/chuva_agora"
                    st.write(f"""
                            <div style="color: black; line-height: 1;">
                                <p style="text-align: center; font-size: 12px; margin: 0; padding: 0;">Fonte: Chuva agora - <a href="{url_sib}" target="_blank"> SIBH</a></p>
                            </div>
                            """,
                        unsafe_allow_html=True)

                    
                    # Usar o valor do session_state diretamente
                    user_input = st.text_area(
                        "Análise das redes Telemétrica", 
                        value=st.session_state.user_input_slide5_seca,
                        height=100,
                        key="text_area_seca"
                    )
                    if user_input != st.session_state.user_input_slide5_seca:
                        st.session_state.user_input_slide5_seca = user_input

                with colun3:    
                    csv = df_seca.to_csv(index=False).encode('utf-8')
                
                    st.download_button(
                        label="⎙",
                        data=csv,
                        file_name='fluviometria_estiagem.csv',
                        mime='text/csv'
                    )

            st.write(" ")
            st.write(" ")
            st.write(" ")
            st.write(" ")
            st.write(" ")
            st.write(" ")
            st.write(" ")   

        return user_input              

async def capa_boletim():
    with capa_boletim_container:

            
        col_logo_1, col_logo_2, col_logo_3 = st.columns([0.4, 1.50, 0.30])
        # st.markdown("""
        #     <style>
        #     /* Remove fundo do date input */
        #     div[data-baseweb="input"] > div {
        #         background-color: #FFFFFF !important;
        #         color: #333333 !important;
        #     }

        #     /* Texto dentro do date picker */
        #     input[type="text"] {
        #         background-color: #FFFFFF !important;
        #         color: #333333 !important;
        #     }

        #     /* Label do date_input */
        #     label {
        #         color: #333333 !important;
        #         font-weight: bold;
        #     }
        #     </style>
        # """, unsafe_allow_html=True)
        # with col_logo_2:
        #     data_inicial = datetime.today()
        #     data_final = data_inicial - timedelta(days=1)
        #     ano_atual = data_inicial.year
        #     jan_1 = date(ano_atual, 1, 1)
        #     dec_31 = date(ano_atual, 12, 31)

        #     intervalo = st.date_input(
        #         "Intervalo de data para gerar o Boletim",
        #         (data_final, data_inicial),  # valor inicial
        #         min_value=jan_1,
        #         max_value=dec_31,
        #         format="DD.MM.YYYY",
        #     )
        #     st.session_state.intervalo = intervalo

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
                <h1  style="font-size: 18px;">Sistema Alto Tietê - Estiagem</h1>
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

            styled_df = tabela.style\
            .set_table_attributes('style="width:100%; table-layout:fixed"')\
            .set_table_styles([
                {"selector": "thead th", "props": [("background-color", "#f0f0f0"), ("color", "#333333"), ("font-size", "14px"), ("padding", "5px 5px"),("text-align", "center")]},
                {"selector": "tbody td", "props": [("background-color", "white"), ("color", "black"), ("font-size", "14px"), ("padding", "5px 5px"), ("text-align", "center"), ("line-height", "3.0")]},
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
            

            html_tabela = styled_df.to_html()

            soup = BeautifulSoup(html_tabela, 'html.parser')
            caption = soup.find('caption')
            if caption:
                caption.decompose()

            html_sem_titulo = str(soup)

            os.makedirs("imagens", exist_ok=True)
            caminho_imagem = "imagens/tabela_alto_tiete.png"
            if os.path.exists(caminho_imagem):
                os.remove(caminho_imagem)
            hti = Html2Image(
                    custom_flags=[
                    "--headless=new",
                    "--disable-gpu",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--force-device-scale-factor=3"
                ]
                )
            hti.output_path = "imagens"  # ou outro diretório
            chrome_path = localizar_chrome()
            hti.browser_path = chrome_path
            hti.screenshot(html_str=html_sem_titulo, save_as=f'tabela_alto_tiete.png', size=(800, 600))

        colun1, colun2 = st.columns([1.0, 1.0])

        with colun1:
            st.write("""
                <div style="text-align: center; color: #333333;">
                    <h1  style="font-size: 14px; margin: 0; padding: 0">Dados do sistema Alto Tietê</h1>
                </div>
                """,
            unsafe_allow_html=True)
            st.write(" ")
            st.markdown(styled_df.to_html(), unsafe_allow_html=True)

            st.write(f"""
                <div style="color: black; line-height: 1;">
                    <p style="text-align: center; font-size: 12px; margin: 0; padding: 0;">Fonte: SSSD Alto Tietê - <a href="{url}" target="_blank"> CTH - DAEE </a></p>
                </div>
                """,
            unsafe_allow_html=True)
        

        with colun2:
            st.write("""
                <div style="text-align: center; color: #333333;">
                    <h1  style="font-size: 14px; margin: 0; padding: 0">Diagrama unifiliar do Alto Tietê</h1>
                </div>
                """,
            unsafe_allow_html=True)
            # imagem = capturar_tela(url)
            # imagem_recortada = imagem.crop((30, 1860, 1230, 2500)) #esquerda, cima, direita, baixo
            data_inicial = datetime.today()
            data_str = data_inicial.strftime('%Y-%m-%d')


            image_path = f'results/imagem_alto_tiete_{data_str}.png'

            if os.path.exists(image_path):
                imagem_recortada = Image.open(image_path)
                
            else:
                imagem_alto_tiete = capturar_tela(url)
                imagem_recortada = imagem_alto_tiete.crop((30, 1860, 1230, 2500))
                output_alto_tiete = os.path.join("results", f"imagem_alto_tiete_{data_str}.png")
                imagem_recortada.save(output_alto_tiete)
                imagem_recortada = Image.open(image_path)

            st.image(imagem_recortada, caption="", use_container_width=True)

            st.write(f"""
                <div style="color: black; line-height: 1;">
                    <p style="text-align: center; font-size: 12px; margin: 0; padding: 0;">Fonte: SSSD Alto Tietê - <a href="{url}" target="_blank"> CTH - DAEE </a></p>
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
            
            user_input = st.text_area("Análise do Sistema Produtor - Alto Tietê", height=100, key="user_input_slide6_seca")
        
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

        return user_input

async def escolha_reservatorio():
    with escolha_reservatorio_container:
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
        if col1.button("Mananciais Sabesp", use_container_width=True):
            st.session_state.reservatorio = "Sabesp"
            st.session_state.selecionado = True
            
        if col2.button("Dados SSD", use_container_width=True):
            st.session_state.reservatorio = "SSD"
            st.session_state.selecionado = True

async def dashboard_reservatorios(): 
    with escolha_reservatorio_container:
        col1, col2, col3 = st.columns([0.30, 1.5, 0.30])

        with col3:
            st.markdown('<div class="align-right">', unsafe_allow_html=True)
            st.image("SP-4.png", caption="", width=300)
            st.markdown('</div>', unsafe_allow_html=True)

        coluna1, coluna2, coluna3 = st.columns([0.2, 1.5, 0.2])

        data_atual = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
        data_formatada = data_atual.strftime("%d/%m/%Y")
        dia = data_atual.day
        mes = data_atual.month
        data_ano_anterior = datetime.today() - timedelta(days=365)
        data_7dias = datetime.today() - timedelta(days=7)
        data_14dias = datetime.today() - timedelta(days=14)
        data_21dias = datetime.today() - timedelta(days=21)

        data_atual_str = data_atual.strftime('%Y-%m-%d')
        data_ano_anterior_str = data_ano_anterior.strftime('%Y-%m-%d')
        data_7dias_str = data_7dias.strftime('%Y-%m-%d')
        data_14dias_str = data_14dias.strftime('%Y-%m-%d')
        data_21dias_str = data_21dias.strftime('%Y-%m-%d')

        data_fim = str(data_ano_anterior.year + 1)
        lista_anos = pd.date_range(start="2000", end=data_fim, freq="Y")
        lista_anos_int = lista_anos.year.tolist()
        lista_anos_int.sort(reverse=True)  # do maior para o menor
        lista_anos_str = list(map(str, lista_anos_int))


        with col2:
            st.write(f"""
            <div style="color: black; display: flex; justify-content: center; align-items: center; padding: 20px;">
                <h1  style="font-size: 22px;">Situação dos Reservatórios da RMSP em {data_formatada}</h1>
            </div>
            """,
            unsafe_allow_html=True)


        if 'data_filter' not in st.session_state:
            st.session_state.data_filter = str(data_ano_anterior.year)

        ano_usado = st.session_state.data_filter
        ano_filtro = f'{ano_usado}-{mes:02d}-{dia:02d}'

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
        st.markdown(button_style, unsafe_allow_html=True)

        creat_dashboard(lista_anos_str, data_atual_str, st.session_state.get("data_ano_anterior_str", data_ano_anterior_str), dia, mes, ano_usado, data_7dias_str, data_14dias_str, data_21dias_str)

        return None


def safe(result, default=None):
    return result if not isinstance(result, Exception) else default

async def main():
    st.sidebar.title("Selecionar visualização")


    if 'sidebar_visual' not in st.session_state:
        st.session_state.sidebar_visual = None

    opcoes = ("Dashboard Reservatórios", "Boletins")

    sidebar_option = st.sidebar.radio(
        "Escolha o tipo visualização:",
        opcoes,
        index=0 if "sidebar_visual" not in st.session_state or st.session_state.sidebar_visual not in opcoes 
            else opcoes.index(st.session_state.sidebar_visual)
    )

    st.session_state.sidebar_visual = sidebar_option

    if st.session_state.sidebar_visual == 'Boletins':

        # Se ainda não logou
        if "logged_in" not in st.session_state:
            st.session_state.logged_in = False

        if not st.session_state.logged_in:
            st.title("🔒 Login")
            username = st.text_input("Usuário")
            password = st.text_input("Senha", type="password")
            if st.button("Entrar"):
                                    
                if username in users_dict and users_dict[username] == password:
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.success("Login bem-sucedido ✅")
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos")
        else:
            st.sidebar.success(f"Bem-vindo, {st.session_state.username}")
            
            if 'boletim' not in st.session_state:
                    # Se ainda não tiver boletim escolhido, exibe a tela de seleção
                    await capa_boletim()

            if "boletim" not in st.session_state or st.session_state.boletim is None:
                st.stop()    
            # Executa todas as tasks simultaneamente
            if st.session_state.boletim == 'chuvas':

                results = await asyncio.gather(
                    capa(),
                    slide1(),
                    slide2(),
                    slide3(),
                    slide5(),
                    slide6(),
                    slide7(),
                    slide8(),
                    return_exceptions=True
                )

                for r in results:
                    if isinstance(r, st.runtime.scriptrunner.RerunException):
                        raise r
                (
                    capa_data, 
                    slide1_data, 
                    slide2_data, 
                    slide3_data, 
                    slide5_data, 
                    slide6_data, 
                    slide7_data, 
                    slide8_data
                ) = results

                slide1_data = safe(slide1_data)
                slide2_data = safe(slide2_data)
                slide3_data = safe(slide3_data)
                slide5_data = safe(slide5_data, (None, None))  # pq esse retorna tupla
                slide6_data = safe(slide6_data)
                slide7_data = safe(slide7_data)
                slide8_data = safe(slide8_data, (None, None, None))  # pq retorna triplo

                user_input1 = slide1_data
                user_input3 = slide3_data
                user_input5, all_extravasamento = slide5_data
                user_input6 = slide6_data
                user_input7 = slide7_data
                image, user_input8, url = slide8_data

                if image.mode == 'P':
                    image_convert = image.convert('RGB')
                else:
                    image_convert = image

                if st.button("Exportar para PDF"):

                    pdf = create_pdf(user_input1=user_input1, image=image_convert, user_input3=user_input3, user_input5=user_input5, all_extravasamento=all_extravasamento, user_input6 = user_input6, user_input7 = user_input7, user_input8=user_input8, url = url)
                    
                    pdf_bytes = pdf.output(dest='S').encode('latin1')

                    st.download_button(
                        label="Baixar PDF",
                        data=pdf_bytes,
                        file_name=f"boletim_diario_{datetime.today().strftime('%Y%m%d')}.pdf",
                        mime="application/pdf",
                    )

            elif st.session_state.boletim == 'secas':
                
                results = await asyncio.gather(
                    capa(),    
                    slide1_seca(),
                    slide1(),
                    slide2(),
                    slide5_seca(),
                    slide6(),
                    slide6_seca(),
                    slide8_seca(),
                    return_exceptions=True
                )

                for r in results:
                    if isinstance(r, st.runtime.scriptrunner.RerunException):
                        raise r
                    
                (
                    capa_data, 
                    slide1_data_seca, 
                    slide1_data, 
                    slide2_data, 
                    slide5_data_seca, 
                    slide6_data, 
                    slide6_data_seca, 
                    slide8_data_seca
                ) = results
                
                slide1_data_seca = safe(slide1_data_seca)
                slide1_data = safe(slide1_data)
                slide2_data = safe(slide2_data)
                slide5_data_seca = safe(slide5_data_seca)  # pq esse retorna tupla
                slide6_data = safe(slide6_data)
                slide6_data_seca = safe(slide6_data_seca)
                slide8_data_seca = safe(slide8_data_seca, (None, None, None))  # pq retorna triplo

                user_input1_seca = slide1_data_seca
                user_input1 = slide1_data
                user_input5_seca = slide5_data_seca
                user_input6 = slide6_data
                user_input6_seca = slide6_data_seca
                image, user_input8_seca, url = slide8_data_seca

                if image.mode == 'P':
                    image_convert = image.convert('RGB')
                else:
                    image_convert = image

                if st.button("Exportar para PDF"):

                    pdf = create_pdf_estiagem(user_input1_seca=user_input1_seca, user_input1=user_input1, user_input5_seca=user_input5_seca, user_input6 = user_input6, user_input6_seca = user_input6_seca, image=image_convert, user_input8_seca=user_input8_seca, url = url)
                    
                    pdf_bytes = pdf.output(dest='S').encode('latin1')

                    st.download_button(
                        label="Baixar PDF",
                        data=pdf_bytes,
                        file_name=f"boletim_diario_{datetime.today().strftime('%Y%m%d')}.pdf",
                        mime="application/pdf",
                    )

    elif st.session_state.sidebar_visual == 'Dashboard Reservatórios':
        dashboards = await asyncio.gather(
            dashboard_reservatorios()
        )

    
if __name__ == "__main__":
    asyncio.run(main())

