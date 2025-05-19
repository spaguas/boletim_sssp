import pandas as pd
import requests
import os
from osgeo import gdal, ogr, osr
from rasterstats import zonal_stats
import geopandas as gpd
from datetime import datetime, timedelta, time

class Interpolation:

    def __init__(self):
        pass

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
            print("Erro: Não há dados válidos para interpolação após a exclusão.")
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
            print(f"Erro: O raster intermediário {output_raster} não foi criado.")
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
        

        # data_stats_shp = data_stats.rename(columns={f"{estatistica_desejada}_precipitation": "rain"})
        data_stats.to_file(f"./results/acumulado_24_mun_{data_hora_final.strftime('%Y-%m-%d')}.shp", driver="ESRI Shapefile")

    @staticmethod
    def main():
        sp_border = gpd.read_file('./data/DIV_MUN_SP_2021a.shp').to_crs(epsg=4326)
        sp_border_shapefile = "results/sp_border.shp"
        municipio_arquivo = 'cities_idw'
        excluir_prefixos = ""

        Interpolation.gerar_mapa_chuva_shapefile(excluir_prefixos, sp_border, sp_border_shapefile, municipio_arquivo)

