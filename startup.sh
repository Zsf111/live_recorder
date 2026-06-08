#!/bin/bash
set -e

# Map POSTGRES_* env vars (standard postgres image) to DB_* env vars (used by Python app)
export DB_NAME="${DB_NAME:-${POSTGRES_DB:-live_recorder}}"
export DB_USER="${DB_USER:-${POSTGRES_USER:-postgres}}"
export DB_PASSWORD="${DB_PASSWORD:-${POSTGRES_PASSWORD?required}}"
export DB_HOST="${DB_HOST:-localhost}"
export DB_PORT="${DB_PORT:-5432}"

# Initialize PostgreSQL data directory if empty (first run)
if [ ! -f "$PGDATA/PG_VERSION" ]; then
    echo "[init] Initializing PostgreSQL data directory..."
    initdb -D "$PGDATA" -U "$DB_USER" --pwfile=<(echo "$DB_PASSWORD")
    echo "host all all 0.0.0.0/0 md5" >> "$PGDATA/pg_hba.conf"
    echo "listen_addresses='*'" >> "$PGDATA/postgresql.conf"
fi

# Start PostgreSQL in background
echo "[pg] Starting PostgreSQL..."
pg_ctl -D "$PGDATA" -l "$PGDATA/logfile" start

export PGPASSWORD="$DB_PASSWORD"

# Wait until PostgreSQL accepts connections
until pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres; do
    echo "[pg] Waiting for PostgreSQL..."
    sleep 1
done

# Create application database on first run
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -tc \
    "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1 || \
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c \
    "CREATE DATABASE $DB_NAME OWNER $DB_USER;"

echo "[init] Running database migrations..."
python3 /app/init_db.py

# Trap termination signals to cleanly stop PostgreSQL
cleanup() {
    echo "[pg] Stopping PostgreSQL..."
    pg_ctl -D "$PGDATA" stop -m fast
    exit 0
}
trap cleanup SIGTERM SIGINT

# Run monitor in background and wait (keep shell as PID 1 for signal handling)
echo "[app] Starting live monitor..."
python3 -u /app/monitor.py &

# Start web panel
echo "[web] Starting web panel on :5000..."
python3 -u /app/web.py &
wait
