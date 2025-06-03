FROM python:3.11

# 1) Системные зависимости
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    unzip \
    wget \
    xvfb \
    x11-xserver-utils \
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
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libxtst6 \
    libxshmfence1 \
    libgl1-mesa-glx \
    libglx-mesa0 \
    libglx0 \
    libglu1-mesa \
    mesa-utils \
    python3-dev \
    git \
    x11vnc \
    fluxbox \
    supervisor \
    netcat-openbsd \
    dbus-x11 \
    dbus \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN apt-get update && apt-get install -y netcat-openbsd

# 2) Установка Google Chrome
RUN wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    apt-get update && \
    apt-get install -y ./google-chrome-stable_current_amd64.deb || apt-get -f install -y && \
    rm ./google-chrome-stable_current_amd64.deb && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# 3) Установка noVNC + websockify
RUN git clone https://github.com/novnc/noVNC.git /opt/novnc && \
    git clone https://github.com/novnc/websockify /opt/novnc/utils/websockify && \
    ln -s /opt/novnc/vnc.html /opt/novnc/index.html

# 4) Создание Chrome wrapper script
RUN echo '#!/bin/bash\n\
export DISPLAY=:0\n\
exec /usr/bin/google-chrome \
    --no-sandbox \
    --disable-dev-shm-usage \
    --disable-gpu \
    --disable-software-rasterizer \
    --disable-background-timer-throttling \
    --disable-backgrounding-occluded-windows \
    --disable-renderer-backgrounding \
    --disable-extensions \
    --disable-plugins \
    --disable-default-apps \
    --disable-sync \
    --disable-translate \
    --hide-scrollbars \
    --mute-audio \
    --no-first-run \
    --safebrowsing-disable-auto-update \
    --ignore-certificate-errors \
    --ignore-ssl-errors \
    --ignore-certificate-errors-spki-list \
    --disable-web-security \
    --disable-features=VizDisplayCompositor \
    --disable-ipc-flooding-protection \
    --user-data-dir=/tmp/chrome-profile \
    "$@"' > /usr/bin/chrome-wrapper && \
    chmod +x /usr/bin/chrome-wrapper

# 5) Environment variables
ENV DISPLAY=:0
ENV CHROME_BIN=/usr/bin/google-chrome
ENV CHROME_PATH=/usr/bin/google-chrome

# 6) Рабочая директория
WORKDIR /app

# 7) Установка Python-зависимостей
COPY captcha_watcher/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 8) Копируем код
COPY . /app

# 9) Конфиг supervisord
COPY captcha_watcher/supervisord.conf /etc/supervisord.conf

# 10) Создание каталогов
RUN mkdir -p /app/shared_volume /app/cookies /tmp/runtime-root /var/log/supervisor /var/run/dbus && \
    chmod 700 /tmp/runtime-root

# 11) Директория для Chrome-профиля
RUN mkdir -p /tmp/chrome-profile && \
    chmod 755 /tmp/chrome-profile

# 12) Копируем или создаём auto_connect.html
RUN echo "🔍 Checking for auto_connect.html file..." && \
    if [ -f /app/captcha_watcher/assets/auto_connect.html ]; then \
        echo "✅ Found custom auto_connect.html, copying to /opt/novnc/"; \
        cp /app/captcha_watcher/assets/auto_connect.html /opt/novnc/auto_connect.html; \
        echo "📝 File copied successfully"; \
    else \
        echo "⚠️ Custom auto_connect.html not found, creating stub in /opt/novnc"; \
        echo '<!DOCTYPE html><html><head><meta charset="utf-8"><title>VNC Auto Connect</title></head><body><p>Auto-connect page missing</p></body></html>' \
        > /opt/novnc/auto_connect.html; \
    fi

# 13) Права и финальная проверка
RUN chmod -R 755 /opt/novnc && \
    chmod 644 /opt/novnc/auto_connect.html && \
    echo "📁 Final file check:" && \
    ls -la /opt/novnc/auto_connect.html && \
    echo "📄 File size:" && \
    wc -c /opt/novnc/auto_connect.html

# 14) Открытые порты
EXPOSE 5900 6080

# 15) Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:6080/ && nc -z localhost 5900 || exit 1

# 16) Запуск supervisor
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisord.conf"]