# Live Recorder

Bilibili / Twitch 全自动直播录制监控系统，单 Docker 容器部署。

## 架构

```
┌─────────── live_recorder ───────────┐
│  startup.sh                         │
│  ├─ pg_ctl start (PostgreSQL 16)   │
│  ├─ 等待就绪 → init_db.py 建表    │
│  ├─ monitor.py & (60s 轮询扫描)    │
│  │    ├─ yt-dlp → B 站直播流拉取   │
│  │    └─ streamlink → Twitch 拉取   │
│  └─ web.py &     (Flask :5000)     │
│       └─ Web 管理面板               │
│                                     │
│  ← 5432 (PostgreSQL)               │
│  ← 8080 (Web 面板)                 │
│  ← ./postgres_data (数据持久化)    │
│  ← ./downloads (录播文件)          │
└─────────────────────────────────────┘
```

## 部署

### 方式一：源码构建

```bash
git clone https://github.com/Zsf111/live_recorder.git
cd live_recorder
echo "DB_PASSWORD=你的密码" > .env
docker compose up -d
```

### 方式二：Docker Hub 镜像

无需 clone 源码，直接拉镜像运行：

```bash
docker run -d --name live_recorder \
  -p 8080:5000 \
  -e DB_PASSWORD=你的密码 \
  -v /你的路径/数据:/var/lib/postgresql/data \
  -v /你的路径/下载:/app/downloads \
  onedosanshi/live_recorder:latest
```

> 镜像地址：[hub.docker.com/r/onedosanshi/live_recorder](https://hub.docker.com/r/onedosanshi/live_recorder)

## Web 管理面板

部署后访问 `http://公网IP:8080`，登录密码为 `DB_PASSWORD`。可在浏览器中完成仪表盘查看、主播管理、录播下载等操作。

## CLI 管理主播

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

## 本地同步

录制完成后，文件自动移入 `downloads/completed/`。在本地执行 `sync.sh` 拉取：

```bash
# 1. 编辑 sync.sh，填好 SERVER / USER / 路径
# 2. 执行拉取（拉完自动删除服务器源文件）
./sync.sh

# 3. 定时自动拉取（每 30 分钟）
crontab -e
# 添加：
*/30 * * * * /path/to/sync.sh >> /path/to/sync.log 2>&1
```

> 拉取依赖 SSH 免密登录。先执行 `ssh-copy-id root@你的服务器IP`。

## 数据库

- `t_streamer_config` — 主播配置（room_id, name, platform, 监控开关, 状态）
- `t_record_log` — 录制日志（起止时间, 文件路径, 状态）
