from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium import webdriver
import tempfile

class Webscrapping:

    def start_session(self):

        temp_user_data_dir = tempfile.mkdtemp()
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=chrome") # Modo sem interface gráfica
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size={},{}".format(1300, 2000)) #largura, altura
        options.add_argument("--disable-web-security")  # Desabilitar CORS
        options.add_argument(f'--user-data-dir={temp_user_data_dir}') 
        
        service = Service(ChromeDriverManager().install(), port=62108)
        driver = webdriver.Chrome(options=options, service=service)

        return driver
    
    # def download(self, url, ref)