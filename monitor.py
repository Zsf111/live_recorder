import os
import subprocess
import time
from datetime import datetime
from typing import Any

import psycopg2

DOWNLOAD_DIR = os.environ.get("DOWNLOAD_DIR", "downloads")
PROXY = os.environ.get("HTTP_PROXY", "")

# {room_id: {"process": Popen, "log_id": int}}
recording_processes = {}
last_report_time = time.time()


def _connect():
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=os.environ.get("DB_PORT", "5432"),
        database=os.environ.get("DB_NAME", "live_recorder"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ["DB_PASSWORD"],
    )


def get_monitored_streamers() -> list[tuple[Any, ...]]:
    connection = _connect()
    cursor = connection.cursor()
    cursor.execute(
        "SELECT room_id, streamer_name, platform FROM t_streamer_config WHERE is_monitored = TRUE"
    )
    streamers = cursor.fetchall()
    cursor.close()
    connection.close()
    return streamers


def update_streamer_status(room_id: str, status: str) -> None:
    """
    Status sync: persist the recording status to the Postgres database
    """
    try:
        connection = _connect()
        cursor = connection.cursor()
        # 更新我们在 Docker 里刚刚 ALTER 拓宽的 current_status 字段
        cursor.execute(
            "UPDATE t_streamer_config SET current_status = %s WHERE room_id = %s",
            (status, room_id),
        )
        connection.commit()  # DML 语句必须 commit 才能真正写入磁盘
        cursor.close()
        connection.close()
        print(f"[DB Sync] Successfully updated streamer ({room_id}) status to: {status}")
    except Exception as e:
        print(f"[DB Sync Failed]: {e}")


def insert_record_log(room_id: str, start_time: datetime, file_path: str) -> int | None:
    try:
        connection = _connect()
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO t_record_log (room_id, start_time, file_path, status) VALUES (%s, %s, %s, 'RECORDING') RETURNING id",
            (room_id, start_time, file_path),
        )
        row = cursor.fetchone()
        if row is None:
            raise Exception("INSERT returned no id, check if the table exists")
        log_id = row[0]
        connection.commit()
        cursor.close()
        connection.close()
        return log_id
    except Exception as e:
        print(f"[DB] Failed to insert record log: {e}")
        return None


def update_record_log(log_id: int, end_time: datetime, status: str) -> None:
    try:
        connection = _connect()
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE t_record_log SET end_time = %s, status = %s WHERE id = %s",
            (end_time, status, log_id),
        )
        connection.commit()
        cursor.close()
        connection.close()
    except Exception as e:
        print(f"[DB] Failed to update record log: {e}")


def check_live_status(room_id: str, platform: str) -> bool:
    try:
        if platform.lower() == "bilibili":
            url = f"https://live.bilibili.com/{room_id}"
            result = subprocess.run(
                ["yt-dlp", "-g", url],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=15,
            )
        elif platform.lower() == "twitch":
            url = f"https://www.twitch.tv/{room_id}"
            cmd = ["streamlink"]
            if PROXY:
                cmd += ["--http-proxy", PROXY]
            cmd += [url, "best", "--stream-url"]
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=15,
            )
        else:
            return False

        if result.returncode == 0 and (
            "m3u8" in result.stdout or "http" in result.stdout
        ):
            return True
        return False
    except Exception:
        return False


def start_recording(room_id: str, name: str, platform: str) -> None:
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(DOWNLOAD_DIR, f"{name}_{timestamp}.mp4")

    print(f"Preparing to start background recording for [{name}]...")

    if platform.lower() == "bilibili":
        url = f"https://live.bilibili.com/{room_id}"
        # Use the tested traditional HTTP live stream filter command
        cmd = ["yt-dlp", "-f", "best[protocol^=http]", "-o", output_path, url]

    elif platform.lower() == "twitch":
        url = f"https://www.twitch.tv/{room_id}"
        cmd = ["streamlink"]
        if PROXY:
            cmd += ["--http-proxy", PROXY]
        cmd += [url, "best", "-o", output_path]
    else:
        return

    try:
        process = subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

        now = datetime.now()
        log_id = insert_record_log(room_id, now, output_path)

        recording_processes[room_id] = {"process": process, "log_id": log_id}
        print(f"Recording process started! Streaming to: {output_path}")

        update_streamer_status(room_id, "RECORDING")

    except Exception as e:
        print(f"Failed to start recording subprocess: {e}")


def clean_finished_processes() -> None:
    """
    Process reaper: periodically check if background recording processes have finished
    """
    finished_rooms = []
    for room_id, info in recording_processes.items():
        if info["process"].poll() is not None:
            finished_rooms.append(room_id)
            print(f"Detected streamer ({room_id}) recording process has exited.")

    for room_id in finished_rooms:
        info = recording_processes[room_id]
        now = datetime.now()
        update_record_log(info["log_id"], now, "SUCCESS")
        del recording_processes[room_id]
        update_streamer_status(room_id, "OFFLINE")


def report_current_status(streamers: list[tuple[Any, ...]]) -> None:
    """
    Periodic status report every 10 minutes
    """
    print("\n" + "=" * 20 + " 10-Minute Status Report " + "=" * 20)
    current_time_str = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"汇报时间: {current_time_str}")
    print(f"当前总录制任务数: {len(recording_processes)}")
    print("-" * 50)

    for room_id, name, platform in streamers:
        status = "RECORDING" if room_id in recording_processes else "OFFLINE"
        print(
            f" [{platform.upper()}]  {name:<12} (房间号: {room_id:<8}) ──> 状态: {status}"
        )
    print("=" * 60 + "\n")


def start_monitoring_loop() -> None:
    global last_report_time
    print(
        "[Minimal Log] Multi-Platform Patrol System starting (scan every 60s, report every 10min)..."
    )
    print("--------- Monitoring ---------")

    while True:
        try:
            # 1. 自动收尸
            clean_finished_processes()

            # 2. 捞取名册
            streamers = get_monitored_streamers()

            # 3. 核心探测（除拉起录制和下播外，全程不打印任何多余日志）
            for room_id, name, platform in streamers:
                if room_id in recording_processes:
                    continue  # 正在录制的，静默跳过探测

                is_live = check_live_status(room_id, platform)
                if is_live:
                    start_recording(room_id, name, platform)

            # 4. 检查是否达到了 10 分钟（600秒）的汇报阈值
            if time.time() - last_report_time >= 600:
                report_current_status(streamers)
                last_report_time = time.time()  # 重置汇报时间
                print("--------- 守护中 ---------")

            # 5. 遵照嘱托：小憩 60 秒
            time.sleep(60)

        except KeyboardInterrupt:
            print("\nShutdown signal received! Safely terminating all background download streams...")
            now = datetime.now()
            for room_id, info in recording_processes.items():
                info["process"].terminate()
                update_record_log(info["log_id"], now, "INTERRUPTED")
                update_streamer_status(room_id, "OFFLINE")
            print("All pipelines safely closed. Sentinel signing off!")
            break
        except Exception as e:
            print(f"Main loop exception: {e}")
            time.sleep(10)


if __name__ == "__main__":
    start_monitoring_loop()
