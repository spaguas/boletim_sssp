import pandas as pd
import requests
from datetime import datetime, timedelta
import os

class ScrapeSabesp:

    def __init__(self):
        pass

    @staticmethod
    def main():
        data_atual = datetime.today()
        data_ano_anterior = datetime.today() - timedelta(days=365)
        data_atual_str = data_atual.strftime('%Y-%m-%d')
        data_ano_anterior_str = data_ano_anterior.strftime('%Y-%m-%d')

        url_ano_atual = f"https://mananciais-sabesp.fcth.br/api/Mananciais/Boletins/Mananciais/{data_atual_str}"

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
        }

        df_sistemas = pd.DataFrame(list(dados_sistema.items()), columns=["Sistema", "SistemaId"])

        merged_data_sistemas = pd.merge(merged_data, df_sistemas, on='SistemaId', how='left')
        merged_data_sistemas = merged_data_sistemas.dropna(subset=['Sistema'])
        merged_data_sistemas['Diferença Vol. Anual (%)'] = merged_data_sistemas['VolumePorcentagem'] - merged_data_sistemas['Volume Ano Anterior (%)']

        merged_data_sistemas = merged_data_sistemas.rename(columns={'VolumePorcentagem': 'VolumeAtual (%)', 'Precipitacao': 'Chuva (mm)', 'PrecipitacaoAcumuladaNoMes': 'Acumulado no Mês (mm)', 'PMLTMensal':'Média Histórica (mm)'})

        merged_data_sistemas = merged_data_sistemas[['Sistema', 'VolumeAtual (%)', 'Volume Ano Anterior (%)', 'Diferença Vol. Anual (%)', 'Chuva (mm)', 'Acumulado no Mês (mm)', 'Média Histórica (mm)']]

        merged_data_sistemas["Data"] = data_atual.strftime("%Y-%m-%d")

        caminho_arquivo_json = os.path.join("results", f"sabesp_sistemas.json")

        # Salva o DataFrame como JSON
        merged_data_sistemas.to_json(caminho_arquivo_json, orient='records', force_ascii=False, indent=2)

        print(f"Dados salvos em: {caminho_arquivo_json}")

