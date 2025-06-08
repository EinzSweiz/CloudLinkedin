#!/bin/bash

# 1. Выполняем очистку
/app/captcha_watcher/startup-cleanup.sh

# 2. Запускаем supervisord — основной процесс контейнера
exec supervisord -c /app/captcha_watcher/supervisord.conf
