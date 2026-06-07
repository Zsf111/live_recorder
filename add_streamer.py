import argparse
import psycopg2


DB_CONFIG = {
    "host": "localhost",
    "port": "5432",
    "database": "live_recorder",
    "user": "postgres",
    "password": "zsf3010ghdej",
}

INSERT_SQL = """
INSERT INTO t_streamer_config (room_id, streamer_name, platform, is_monitored)
VALUES (%s, %s, %s, %s)
ON CONFLICT (room_id)
DO UPDATE SET streamer_name = EXCLUDED.streamer_name,
              platform = EXCLUDED.platform,
              is_monitored = EXCLUDED.is_monitored;
"""


# Usage:
#   python add_streamer.py -id 11899478 -n OLDnannan
#   python add_streamer.py -id xqc -n xQcOW -p twitch --no-monitor


def add_streamer(room_id, name, platform, is_monitored):
    connection = psycopg2.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        database=DB_CONFIG["database"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
    )
    cursor = connection.cursor()
    cursor.execute(INSERT_SQL, (room_id, name, platform, is_monitored))
    connection.commit()
    cursor.close()
    connection.close()
    action = "Added/Updated"
    print(f"{action} streamer: [{platform}] {name} (room_id={room_id}) monitored={is_monitored}")


def main():
    parser = argparse.ArgumentParser(description="Manage streamers in live recorder database")
    parser.add_argument("-id", "--room-id", required=True, help="Room ID (e.g. 11899478)")
    parser.add_argument("-n", "--name", required=True, help="Streamer name")
    parser.add_argument("-p", "--platform", default="bilibili", choices=["bilibili", "twitch"], help="Platform (default: bilibili)")
    parser.add_argument("--no-monitor", action="store_true", help="Add but do not monitor this streamer")

    args = parser.parse_args()

    try:
        add_streamer(args.room_id, args.name, args.platform, not args.no_monitor)
    except Exception as e:
        print(f"Failed to add streamer: {e}")


if __name__ == "__main__":
    main()
