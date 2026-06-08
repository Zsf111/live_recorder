#!/bin/bash
# 从服务器拉取已完成录播，拉取成功后删除服务器源文件
set -e

# ========== 按需修改以下配置 ==========
SERVER="your-server-ip"
USER="root"
REMOTE_PATH="/root/live_recorder/downloads/completed"
LOCAL_PATH="./downloads"
# =====================================

mkdir -p "$LOCAL_PATH"

echo "[sync] Pulling completed recordings from $USER@$SERVER:$REMOTE_PATH ..."
rsync -avz --remove-source-files \
    -e "ssh" \
    "$USER@$SERVER:$REMOTE_PATH/" \
    "$LOCAL_PATH/"

echo "[sync] Cleaning empty dirs on server..."
ssh "$USER@$SERVER" "find $REMOTE_PATH -type d -empty -delete 2>/dev/null" || true

echo "[sync] Done."
