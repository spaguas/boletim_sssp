FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Instala dependências do sistema e do Chrome
RUN apt-get update && apt-get install -y \
    wget curl unzip gnupg ca-certificates \
    fonts-liberation libappindicator3-1 libasound2 libatk-bridge2.0-0 libatk1.0-0 \
    libcups2 libdbus-1-3 libgdk-pixbuf2.0-0 libnspr4 libnss3 libx11-xcb1 \
    libxcomposite1 libxdamage1 libxrandr2 xdg-utils lsb-release \
    libgbm1 libgtk-3-0 libxshmfence1 libxi6 libxcursor1 libxinerama1 libgl1 \
    libu2f-udev libvulkan1 libxss1 \
    --no-install-recommends && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Baixa e instala o Google Chrome com a opção --no-check-certificate para ignorar erro de certificado
RUN wget --no-check-certificate https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    apt-get update && apt-get install -y ./google-chrome-stable_current_amd64.deb && \
    rm google-chrome-stable_current_amd64.deb && \
    ln -s /usr/bin/google-chrome /usr/bin/chromium-browser

# Instala o Miniconda
RUN wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh && \
    bash Miniconda3-latest-Linux-x86_64.sh -b -p /opt/conda && \
    rm Miniconda3-latest-Linux-x86_64.sh

ENV PATH="/opt/conda/bin:$PATH"


WORKDIR /usr/src/app_boletim_diario
COPY . /usr/src/app_boletim_diario

RUN conda env create -f environment.yml

SHELL [ "conda","run","-n","boletim_env","/bin/bash","-c" ]

EXPOSE 8501

CMD ["conda", "run", "-n", "boletim_env", "streamlit", "run", "app_boletim_diario.py", "--server.port=8501", "--server.enableCORS=false"]