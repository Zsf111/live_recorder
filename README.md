# Live Recorder

Bilibili / Twitch 全自动直播录制监控系统，单 Docker 容器部署。

## 架构

```
┌─────────── live_recorder ───────────┐
│  startup.sh                         │
│  ├─ pg_ctl start (PostgreSQL 16)   │
│  ├─ 等待就绪 → init_db.py 建表    │
│  └─ monitor.py (60s 轮询扫描)      │
│       ├─ yt-dlp → B 站直播流拉取   │
│       └─ streamlink → Twitch 拉取   │
│                                     │
│  ← 5432 (PostgreSQL)               │
│  ← ./postgres_data (数据持久化)    │
│  ← ./downloads (录播文件)          │
└─────────────────────────────────────┘
```

## 部署

```bash
git clone https://github.com/Zsf111/live_recorder.git
cd live_recorder
echo "DB_PASSWORD=你的密码" > .env
docker compose up -d
```

## 管理主播

```bash
docker exec live_recorder python3 /app/add_streamer.py add -id 11899478 -n OLDnannan -p bilibili
docker exec live_recorder python3 /app/add_streamer.py ls
docker exec live_recorder python3 /app/add_streamer.py edit -id 11899478 -n 新名字
docker exec live_recorder python3 /app/add_streamer.py edit -id 11899478 --no-monitor
docker exec live_recorder python3 /app/add_streamer.py rm -id 11899478
```

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DB_PASSWORD` | 数据库密码 | 无，必填 |
| `DB_HOST` | 数据库地址 | localhost |
| `DB_PORT` | 数据库端口 | 5432 |
| `HTTP_PROXY` | Twitch 代理 | 空（不用） |
| `DOWNLOAD_DIR` | 录播输出路径 | downloads |

## 数据库

- `t_streamer_config` — 主播配置（room_id, name, platform, 监控开关, 状态）
- `t_record_log` — 录制日志（起止时间, 文件路径, 状态）
