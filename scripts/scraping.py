import os
from datetime import datetime, timedelta, time
from PIL import Image, ImageOps
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from PIL import Image
import time as tm
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
import urllib.parse
import tempfile
import shutil
import io
from dotenv import load_dotenv

load_dotenv()

horas = 24
data_inicial = datetime.today()
data_str = data_inicial.strftime('%Y-%m-%d')

class Scraping:
    

    def __init__(self):
        pass

    def iniciar_chrome_com_diretorio_unico(self):
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

        # Inicia o ChromeDriver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(options=options, service=service)

        return driver, unique_user_data_dir



    def capturar_ipmet(self):
        driver, dir_path = self.iniciar_chrome_com_diretorio_unico()
        try:
            usuario = os.environ.get('IPMET_USERNAME')
            senha = os.environ.get('IPMET_PASSWORD')
            url = f"https://www.ipmetradar.com.br/restrito/2login.php?username={usuario}&senha={senha}&tipo_acesso=ip"

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

            driver.save_screenshot("screenshot_ipmet.png")

            img = Image.open("screenshot_ipmet.png")
            imagem_recortada = img.crop((120, 362, 1100, 855))
            output_path = os.path.join("results", f"imagem_ipmet_{data_str.strftime('%Y-%m-%d')}.png")
            imagem_recortada.save(output_path)

        finally:
            driver.quit()
            shutil.rmtree(dir_path, ignore_errors=True)

    def capturar_saisp(self):
        driver, dir_path = self.iniciar_chrome_com_diretorio_unico()
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
            output_path = os.path.join("results", f"imagem_saisp_{data_str.strftime('%Y-%m-%d')}.png")
            imagem_borda.save(output_path)

        finally:
            driver.quit()
            shutil.rmtree(dir_path, ignore_errors=True)


    def capturar_tela(self, url):

        driver, dir_path = self.iniciar_chrome_com_diretorio_unico()
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

    def get_data(self):

        url_rmsp = 'https://cth.daee.sp.gov.br/ssdsp/'
        imagem_rmsp = self.capturar_tela(url_rmsp)
        imagem_rmsp_recorte = imagem_rmsp.crop((90, 945, 1200, 1650))
        output_rmsp = os.path.join("results", f"imagem_rmsp_{data_str.strftime('%Y-%m-%d')}.png")
        imagem_rmsp_recorte.save(output_rmsp)

        url_alto_tiete = 'https://cth.daee.sp.gov.br/ssdsp/Sistema/AltoTiete'
        imagem_alto_tiete = self.capturar_tela(url_alto_tiete)
        imagem_alto_tiete_recortada = imagem_alto_tiete.crop((30, 1860, 1230, 2500))
        output_alto_tiete = os.path.join("results", f"imagem_alto_tiete_{data_str.strftime('%Y-%m-%d')}.png")
        imagem_alto_tiete_recortada.save(output_alto_tiete) 


    def main(self):
        self.capturar_ipmet()
        self.capturar_saisp()
        self.get_data()