FROM python:3.11-slim

LABEL maintainer="danil"

# Устанавливаем зависимости ОС
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    unzip \
    wget \
    xvfb \
    libxi6 \
    libgconf-2-4 \
    libnss3 \
    libxss1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    fonts-liberation \
    libappindicator3-1 \
    x11-utils \
    libgbm1 \
    libvulkan1 \
    xdg-utils \
    python3-dev \
    docker.io \
    docker-compose \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Устанавливаем Google Chrome
RUN wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    apt-get install -y ./google-chrome-stable_current_amd64.deb && \
    rm ./google-chrome-stable_current_amd64.deb

# requirements
COPY requirements.txt /app/requirements.txt
WORKDIR /app
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . /app

# CMD ["python", "parser/engine/runner.py"]
CMD ["python", "manage.py", "runserver", "0.0.0.0:8001"]