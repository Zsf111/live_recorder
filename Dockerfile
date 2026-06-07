FROM postgres:16

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

COPY add_streamer.py init_db.py monitor.py startup.sh ./
RUN chmod +x startup.sh && mkdir -p downloads /app/postgres_data

ENV DB_HOST=localhost \
    DB_PORT=5432 \
    DB_NAME=live_recorder \
    DB_USER=postgres \
    PGDATA=/var/lib/postgresql/data

VOLUME /var/lib/postgresql/data
VOLUME /app/downloads

CMD ["/app/startup.sh"]
