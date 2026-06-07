FROM postgres:16

# APT 国内源加速
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    -r requirements.txt

COPY add_streamer.py init_db.py monitor.py startup.sh ./
RUN chmod +x startup.sh && mkdir -p downloads && chown -R postgres:postgres /app

ENV DB_HOST=localhost \
    DB_PORT=5432 \
    DB_NAME=live_recorder \
    DB_USER=postgres \
    PGDATA=/var/lib/postgresql/data

VOLUME /var/lib/postgresql/data
VOLUME /app/downloads

USER postgres
CMD ["/app/startup.sh"]
