# import os
import subprocess
import time

import psycopg2

# Memory guard dictionary: keeps track of running recording processes to avoid re-launching the same room_id
recording_processes = {}
last_report_time = time.time()


def get_monitored_streamers():
    connection = psycopg2.connect(
        host="localhost",
        port="5432",
        database="live_recorder",
        user="postgres",
        password="zsf3010ghdej",
    )
    cursor = connection.cursor()
    cursor.execute(
        "SELECT room_id, streamer_name, platform FROM t_streamer_config WHERE is_monitored = TRUE"
    )
    streamers = cursor.fetchall()
    cursor.close()
    connection.close()
    return streamers


def update_streamer_status(room_id, status):
    """
    Status sync: persist the recording status to the Postgres database
    """
    try:
        connection = psycopg2.connect(
            host="localhost",
            port="5432",
            database="live_recorder",
            user="postgres",
            password="zsf3010ghdej",
        )
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


def check_live_status(room_id, platform):
    """
    Live status probe: Bilibili via yt-dlp, Twitch via streamlink (proxied)
    """
    LOCAL_PROXY = "http://127.0.0.1:7897"
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
            result = subprocess.run(
                [
                    "streamlink",
                    "--http-proxy",
                    LOCAL_PROXY,
                    url,
                    "best",
                    "--stream-url",
                ],
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


def start_recording(room_id, name, platform):
    """
    Async recording engine
    """
    LOCAL_PROXY = "http://127.0.0.1:7897"
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_path = f"downloads/{name}_{timestamp}.mp4"

    print(f"Preparing to start background recording for [{name}]...")

    if platform.lower() == "bilibili":
        url = f"https://live.bilibili.com/{room_id}"
        # Use the tested traditional HTTP live stream filter command
        cmd = ["yt-dlp", "-f", "best[protocol^=http]", "-o", output_path, url]

    elif platform.lower() == "twitch":
        url = f"https://www.twitch.tv/{room_id}"
        cmd = [
            "streamlink",
            "--http-proxy",
            LOCAL_PROXY,
            url,
            "best",
            "-o",
            output_path,
        ]
    else:
        return

    try:
        # 挂起异步子进程，并将输出导向 DEVNULL 保持控制台干净
        process = subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

        # 1. 更新 Python 内存字典
        recording_processes[room_id] = process
        print(f"Recording process started! Streaming to: {output_path}")

        # Sync to Postgres: update status to RECORDING
        update_streamer_status(room_id, "RECORDING")

    except Exception as e:
        print(f"Failed to start recording subprocess: {e}")


def clean_finished_processes():
    """
    Process reaper: periodically check if background recording processes have finished
    """
    finished_rooms = []
    for room_id, process in recording_processes.items():
        # poll() 不为 None 代表进程已经结束（主播下播或断流）
        if process.poll() is not None:
            finished_rooms.append(room_id)
            print(f"Detected streamer ({room_id}) recording process has exited.")

    for room_id in finished_rooms:
        # 1. 从 Python 内存字典中踢出
        del recording_processes[room_id]
        # Sync to Postgres: update status back to OFFLINE
        update_streamer_status(room_id, "OFFLINE")


def report_current_status(streamers):
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


def start_monitoring_loop():
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
            for room_id, process in recording_processes.items():
                process.terminate()
                update_streamer_status(room_id, "OFFLINE")
            print("All pipelines safely closed. Sentinel signing off!")
            break
        except Exception as e:
            print(f"Main loop exception: {e}")
            time.sleep(10)


if __name__ == "__main__":
    start_monitoring_loop()
