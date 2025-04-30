FROM continuumio/miniconda3

WORKDIR /usr/src/app_boletim_diario
COPY . /usr/src/app_boletim_diario

RUN conda env create -f environment.yml

SHELL [ "conda","run","-n","boletim_env","/bin/bash","-c" ]

EXPOSE 8501

CMD ["conda", "run", "-n", "boletim_env", "streamlit", "run", "app_boletim_diario.py", "--server.port=8501", "--server.enableCORS=false"]