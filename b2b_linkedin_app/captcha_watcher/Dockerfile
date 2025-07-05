FROM python:3.11
# 1) Установка системных зависимостей
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
    xterm \
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
    libgl1-mesa-dri \
    mesa-utils \
    python3-dev \
    git \
    fluxbox \
    supervisor \
    netcat-openbsd \
    dbus-x11 \
    net-tools \
    dbus \
    fonts-dejavu-core \
    fonts-liberation \
    libgtk2.0-0 \
    libgbm-dev \
    libnotify-dev \
    libnss3-dev \
    libdrm2 \
    docker.io \
    docker-compose && \
    apt-get clean && rm -rf /var/lib/apt/lists/*
# 2) Установка TigerVNC (включает x0vncserver)
RUN apt-get update && \
    apt-get install -y tigervnc-scraping-server && \
    apt-get clean && rm -rf /var/lib/apt/lists/*
# 3) Установка Google Chrome
RUN wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    apt-get update && \
    apt-get install -y ./google-chrome-stable_current_amd64.deb || apt-get -f install -y && \
    rm ./google-chrome-stable_current_amd64.deb && \
    apt-get clean && rm -rf /var/lib/apt/lists/*
# 4) Установка noVNC + websockify
RUN git clone https://github.com/novnc/noVNC.git /opt/novnc && \
    ln -s /opt/novnc/vnc.html /opt/novnc/index.html && \
    pip install websockify
# 5) Подготовка окружения
RUN touch /tmp/.Xauthority && chmod 600 /tmp/.Xauthority
# 6) Chrome wrapper
RUN echo '#!/bin/bash\n\
export DISPLAY=:0\n\
export XAUTHORITY=/tmp/.Xauthority\n\
xhost +local:root\n\
exec /usr/bin/google-chrome \
    --no-sandbox \
    --disable-dev-shm-usage \
    --disable-gpu \
    --disable-software-rasterizer \
    --disable-features=VizDisplayCompositor \
    --disable-extensions \
    --disable-background-networking \
    --no-first-run \
    --no-default-browser-check \
    --disable-background-timer-throttling \
    --disable-backgrounding-occluded-windows \
    --disable-renderer-backgrounding \
    --disable-features=TranslateUI \
    --disable-ipc-flooding-protection \
    --remote-debugging-port=9222 \
    --window-size=1200,800 \
    --window-position=0,0 \
    --start-maximized \
    "$@"' > /usr/bin/chrome-wrapper && \
    chmod +x /usr/bin/chrome-wrapper
# 7) Переменные окружения
ENV DISPLAY=:0
ENV CHROME_BIN=/usr/bin/google-chrome
ENV CHROME_PATH=/usr/bin/google-chrome
# 8) Рабочая директория
WORKDIR /app
# 9) Установка Python-зависимостей
COPY captcha_watcher/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
# 10) Копирование кода
COPY . /app
# 11) Конфигурация supervisord
COPY captcha_watcher/supervisord.conf /etc/supervisord.conf
# 12) Создание директорий
RUN mkdir -p /app/shared_volume /app/cookies /tmp/runtime-root /var/log/supervisor /var/run/dbus && \
    chmod 700 /tmp/runtime-root
# 13) Chrome-профиль
RUN mkdir -p /tmp/chrome-profile && chmod 755 /tmp/chrome-profile
# 14) Подключение вспомогательных скриптов
COPY captcha_watcher/startup-cleanup.sh /app/captcha_watcher/startup-cleanup.sh
COPY captcha_watcher/start.sh /app/captcha_watcher/start.sh
COPY captcha_watcher/websockify-wrapper.sh /app/websockify-wrapper.sh
# Исправление окончаний строк для Windows совместимости
RUN sed -i 's/\r$//' /app/captcha_watcher/start.sh
RUN sed -i 's/\r$//' /app/captcha_watcher/startup-cleanup.sh
RUN sed -i 's/\r$//' /app/websockify-wrapper.sh
# Установка прав на выполнение
RUN chmod +x /app/captcha_watcher/start.sh
RUN chmod +x /app/captcha_watcher/startup-cleanup.sh
RUN chmod +x /app/websockify-wrapper.sh
COPY captcha_watcher/assets/auto_connect.html /opt/novnc/auto_connect.html
RUN chmod -R 755 /opt/novnc && chmod 644 /opt/novnc/auto_connect.html
# 15) Порты
EXPOSE 5900 6080
# 16) Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:6080/ && nc -z localhost 5900 || exit 1
# 17) Запуск
ENTRYPOINT ["/bin/bash", "/app/captcha_watcher/start.sh"]