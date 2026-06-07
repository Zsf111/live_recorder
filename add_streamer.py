# Usage:
#   python add_streamer.py add -id 11899478 -n OLDnannan -p bilibili
#   python add_streamer.py add -id xqc -n xQcOW -p twitch --no-monitor
#   python add_streamer.py ls
#   python add_streamer.py edit -id 11899478 -n 新名字
#   python add_streamer.py edit -id 11899478 --no-monitor
#   python add_streamer.py edit -id 11899478 --monitor
#   python add_streamer.py rm -id 11899478

import argparse
import os

import psycopg2

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": os.environ.get("DB_PORT", "5432"),
    "database": os.environ.get("DB_NAME", "live_recorder"),
    "user": os.environ.get("DB_USER", "postgres"),
    "password": os.environ["DB_PASSWORD"],
}


def _connect():
    return psycopg2.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        database=DB_CONFIG["database"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
    )


def cmd_add(room_id: str, name: str, platform: str, is_monitored: bool) -> None:
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO t_streamer_config (room_id, streamer_name, platform, is_monitored)
           VALUES (%s, %s, %s, %s)
           ON CONFLICT (room_id)
           DO UPDATE SET streamer_name = EXCLUDED.streamer_name,
                         platform = EXCLUDED.platform,
                         is_monitored = EXCLUDED.is_monitored""",
        (room_id, name, platform, is_monitored),
    )
    conn.commit()
    cur.close()
    conn.close()
    print(f"Added/Updated: [{platform}] {name} (room_id={room_id}) monitored={is_monitored}")


def cmd_list() -> None:
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT room_id, streamer_name, platform, is_monitored, current_status "
        "FROM t_streamer_config ORDER BY platform, streamer_name"
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        print("(empty)")
        return

    print(f"{'Room ID':<16} {'Name':<20} {'Platform':<10} {'Monitored':<10} {'Status'}")
    print("-" * 75)
    for room_id, name, platform, monitored, status in rows:
        print(
            f"{room_id:<16} {name:<20} {platform:<10} "
            f"{str(monitored):<10} {status or '—'}"
        )


def cmd_delete(room_id: str) -> None:
    conn = _connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM t_streamer_config WHERE room_id = %s", (room_id,))
    deleted = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    if deleted:
        print(f"Deleted streamer: room_id={room_id}")
    else:
        print(f"Not found: room_id={room_id}")


def cmd_edit(
    room_id: str,
    name: str | None,
    platform: str | None,
    is_monitored: bool | None,
) -> None:
    set_parts = []
    values = []
    if name is not None:
        set_parts.append("streamer_name = %s")
        values.append(name)
    if platform is not None:
        set_parts.append("platform = %s")
        values.append(platform)
    if is_monitored is not None:
        set_parts.append("is_monitored = %s")
        values.append(is_monitored)

    if not set_parts:
        print("Nothing to update.")
        return

    values.append(room_id)
    sql = f"UPDATE t_streamer_config SET {', '.join(set_parts)} WHERE room_id = %s"

    conn = _connect()
    cur = conn.cursor()
    cur.execute(sql, values)
    updated = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()

    if updated:
        print(f"Updated streamer: room_id={room_id}")
    else:
        print(f"Not found: room_id={room_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage streamers in live recorder database")
    sub = parser.add_subparsers(dest="command", required=True)

    # ---- add ----
    p_add = sub.add_parser("add", help="Add or update a streamer")
    p_add.add_argument("-id", "--room-id", required=True, help="Room ID")
    p_add.add_argument("-n", "--name", required=True, help="Streamer name")
    p_add.add_argument("-p", "--platform", default="bilibili", choices=["bilibili", "twitch"])
    p_add.add_argument("--no-monitor", action="store_true", help="Do not monitor this streamer")

    # ---- list ----
    sub.add_parser("ls", help="List all streamers")
    sub.add_parser("list", help="List all streamers (alias)")

    # ---- delete ----
    p_rm = sub.add_parser("rm", help="Delete a streamer")
    p_rm.add_argument("-id", "--room-id", required=True, help="Room ID")

    # ---- edit ----
    p_edit = sub.add_parser("edit", help="Update streamer fields")
    p_edit.add_argument("-id", "--room-id", required=True, help="Room ID")
    p_edit.add_argument("-n", "--name", default=None)
    p_edit.add_argument("-p", "--platform", choices=["bilibili", "twitch"], default=None)
    monitor_group = p_edit.add_mutually_exclusive_group()
    monitor_group.add_argument("--no-monitor", action="store_true", default=None, dest="is_monitored")
    monitor_group.add_argument("--monitor", action="store_true", default=None, dest="is_monitored")

    args = parser.parse_args()

    try:
        if args.command in ("add",):
            cmd_add(args.room_id, args.name, args.platform, not args.no_monitor)
        elif args.command in ("ls", "list"):
            cmd_list()
        elif args.command in ("rm",):
            cmd_delete(args.room_id)
        elif args.command in ("edit",):
            cmd_edit(args.room_id, args.name, args.platform, args.is_monitored)
    except Exception as e:
        print(f"Failed: {e}")


if __name__ == "__main__":
    main()
