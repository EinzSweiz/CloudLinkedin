#!/bin/bash

# 1. Выполняем очистку
/app/captcha_watcher/startup-cleanup.sh

# 2. Создаём ready-файл
CONTAINER_ID=$(hostname)
READY_FLAG="/captcha_ready_flags/${CONTAINER_ID}.txt"
mkdir -p /captcha_ready_flags
touch "$READY_FLAG"
echo "[INFO] ✅ CAPTCHA container marked as READY: $READY_FLAG"

# 3. Запускаем supervisord — основной процесс контейнера
exec supervisord -c /app/captcha_watcher/supervisord.conf
