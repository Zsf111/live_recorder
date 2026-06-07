# import os
import subprocess
import time

import psycopg2

# 🧠 内存守护字典：依然保留在内存中，用于控制主循环不要重复拉起同一个room_id
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
    💾 状态回写官：将内存中的录制状态同步持久化到 Postgres 数据库中
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
        print(f"🔄 [DB同步] 成功将主播 ({room_id}) 的数据库状态变更为: {status}")
    except Exception as e:
        print(f"❌ [DB同步失败]: {e}")


def check_live_status(room_id, platform):
    """
    🕵️ 哨兵嗅探逻辑：B站用 yt-dlp，Twitch 走代理用 streamlink
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
    🎬 异步录制引擎
    """
    LOCAL_PROXY = "http://127.0.0.1:7897"
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_path = f"downloads/{name}_{timestamp}.mp4"

    print(f"🛰️ 准备为 【{name}】 开启后台录制管道...")

    if platform.lower() == "bilibili":
        url = f"https://live.bilibili.com/{room_id}"
        # 🌟 黄金重构：精准使用你测试成功的传统 HTTP 直播流过滤命令
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
        print(f"🔴 后台进程已拉起！文件流正实时写入: {output_path}")

        # 2. 🌟 核心修复：同步让大脑通知 Postgres 数据库，状态改为 RECORDING
        update_streamer_status(room_id, "RECORDING")

    except Exception as e:
        print(f"❌ 试图拉起录制子进程失败: {e}")


def clean_finished_processes():
    """
    🧹 进程收尸官：定期轮询后台下载进程是否寿终正寝
    """
    finished_rooms = []
    for room_id, process in recording_processes.items():
        # poll() 不为 None 代表进程已经结束（主播下播或断流）
        if process.poll() is not None:
            finished_rooms.append(room_id)
            print(f"🏁 监测到主播 ({room_id}) 的录制进程已在后台退出。")

    for room_id in finished_rooms:
        # 1. 从 Python 内存字典中踢出
        del recording_processes[room_id]
        # 2. 🌟 核心修复：同步通知 Postgres 数据库，状态回滚为 OFFLINE
        update_streamer_status(room_id, "OFFLINE")


def report_current_status(streamers):
    """
    📊 每10分钟一次的复盘大汇报
    """
    print("\n" + "=" * 20 + " 📊 10分钟定点状态汇报 " + "=" * 20)
    current_time_str = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"汇报时间: {current_time_str}")
    print(f"当前总录制任务数: {len(recording_processes)}")
    print("-" * 50)

    for room_id, name, platform in streamers:
        status = "🔴 RECORDING" if room_id in recording_processes else "💤 OFFLINE"
        print(
            f" [{platform.upper()}]  {name:<12} (房间号: {room_id:<8}) ──> 状态: {status}"
        )
    print("=" * 60 + "\n")


def start_monitoring_loop():
    global last_report_time
    print(
        "🕵️‍♂️ 【极简日志版】两栖巡逻守护系统正式启航（每60秒静默扫描，每10分钟大汇报）..."
    )
    print("--------- 守护中 ---------")

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

            # 4. 🧠 检查是否达到了 10 分钟（600秒）的汇报阈值
            if time.time() - last_report_time >= 600:
                report_current_status(streamers)
                last_report_time = time.time()  # 重置汇报时间
                print("--------- 守护中 ---------")

            # 5. ⏳ 遵照嘱托：小憩 60 秒
            time.sleep(60)

        except KeyboardInterrupt:
            print("\n🛑 收到下班指令！正在安全切断所有后台下载流...")
            for room_id, process in recording_processes.items():
                process.terminate()
                update_streamer_status(room_id, "OFFLINE")
            print("🔒 整个管道已安全关闭，哨兵退线！")
            break
        except Exception as e:
            print(f"⚠️ 系统主循环发生异常: {e}")
            time.sleep(10)


if __name__ == "__main__":
    start_monitoring_loop()
