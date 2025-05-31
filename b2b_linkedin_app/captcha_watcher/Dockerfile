FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
  wget curl unzip git \
  libnss3 libatk1.0-0 libatk-bridge2.0-0 libxss1 \
  libasound2 libgbm-dev libgtk-3-0 libx11-xcb-dev \
  xvfb x11-utils x11vnc fluxbox supervisor \
  gnupg tigervnc-standalone-server \
  && rm -rf /var/lib/apt/lists/*

# Install Google Chrome
RUN wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    apt-get update && \
    apt-get install -y ./google-chrome-stable_current_amd64.deb || apt-get -f install -y && \
    rm ./google-chrome-stable_current_amd64.deb

# Install noVNC + websockify
RUN git clone https://github.com/novnc/noVNC.git /opt/novnc && \
    git clone https://github.com/novnc/websockify /opt/novnc/utils/websockify && \
    ln -s /opt/novnc/vnc.html /opt/novnc/index.html

# Set working directory
WORKDIR /app

# Copy project
COPY . /app

# Copy our custom auto_connect.html to noVNC directory
RUN cp /app/captcha_watcher/assets/auto_connect.html /opt/novnc/auto_connect.html

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Supervisor config
COPY captcha_watcher/supervisord.conf /etc/supervisord.conf

# Create shared dirs
RUN mkdir -p /app/shared_volume /app/cookies

# Set permissions
RUN chmod -R 755 /opt/novnc && \
    chmod 644 /opt/novnc/auto_connect.html

# Expose ports
EXPOSE 5900 6080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
  CMD curl -f http://localhost:6080/ || exit 1

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisord.conf"]