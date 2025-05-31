# Updated captcha_watcher/Dockerfile - Add noVNC web client
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
  wget curl unzip git \
  libnss3 libatk1.0-0 libatk-bridge2.0-0 libxss1 \
  libasound2 libgbm-dev libgtk-3-0 libx11-xcb-dev \
  xvfb x11-utils x11vnc fluxbox supervisor \
  gnupg tigervnc-standalone-server \
  && rm -rf /var/lib/apt/lists/*

# Install Chrome
RUN wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    apt-get update && \
    apt-get install -y ./google-chrome-stable_current_amd64.deb || apt-get -f install -y && \
    rm ./google-chrome-stable_current_amd64.deb

# Install noVNC for web-based VNC access
RUN git clone https://github.com/novnc/noVNC.git /opt/novnc && \
    git clone https://github.com/novnc/websockify /opt/novnc/utils/websockify && \
    ln -s /opt/novnc/vnc.html /opt/novnc/index.html

# Set working directory
WORKDIR /app

# Copy the entire project
COPY . /app

# Install Python dependencies from main project
RUN pip install --no-cache-dir -r requirements.txt

# VNC setup - create directory for root user
RUN mkdir -p /root/.vnc && \
    echo "password" | vncpasswd -f > /root/.vnc/passwd && \
    chmod 600 /root/.vnc/passwd

# Copy supervisor config
COPY captcha_watcher/supervisord.conf /etc/supervisord.conf

# Create shared volume directory
RUN mkdir -p /app/shared_volume /app/cookies

# Expose both VNC and noVNC ports
EXPOSE 5900 6080

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisord.conf"]