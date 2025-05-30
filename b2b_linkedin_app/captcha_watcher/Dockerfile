FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    wget curl unzip \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libxss1 \
    libasound2 libgbm-dev libgtk-3-0 libx11-xcb-dev \
    xvfb x11-utils x11vnc fluxbox supervisor \
    && rm -rf /var/lib/apt/lists/*

# Установка Chrome
RUN wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
 && dpkg -i google-chrome-stable_current_amd64.deb || apt-get -fy install

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . /app
WORKDIR /app

CMD ["python", "captcha_watcher.py"]
