import os

import psycopg2


def _connect():
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=os.environ.get("DB_PORT", "5432"),
        database=os.environ.get("DB_NAME", "live_recorder"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ["DB_PASSWORD"],
    )


def init_database() -> None:
    connection = None
    cursor = None
    try:
        connection = _connect()

        # 2. 创建一个游标（相当于在数据库里敲命令的那个闪烁光标）
        cursor = connection.cursor()
        print("成功连接到本地 Docker PostgreSQL 数据库！")

        # 3. 编写 DDL 建表语句（创建主播配置表）
        # room_id 作为主键，防止同一个主播被录入两次
        create_table_query = """
        CREATE TABLE IF NOT EXISTS t_streamer_config (
            room_id VARCHAR(50) PRIMARY KEY,
            streamer_name VARCHAR(100) NOT NULL,
            platform VARCHAR(30) DEFAULT 'twitch',
            is_monitored BOOLEAN DEFAULT TRUE,
            current_status VARCHAR(20) DEFAULT 'OFFLINE',
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """

        # 4. 让光标执行这条建表命令
        cursor.execute(create_table_query)

        # 5. 创建录播日志表
        create_log_table_query = """
        CREATE TABLE IF NOT EXISTS t_record_log (
            id SERIAL PRIMARY KEY,
            room_id VARCHAR(50) NOT NULL,
            start_time TIMESTAMP NOT NULL,
            end_time TIMESTAMP,
            file_path TEXT,
            audio_path TEXT,
            status VARCHAR(20) DEFAULT 'RECORDING'
        );
        """
        cursor.execute(create_log_table_query)

        # Migration: add audio_path column if upgrading from older schema
        cursor.execute("""
            ALTER TABLE t_record_log
            ADD COLUMN IF NOT EXISTS audio_path TEXT
        """)

        # 6. 核心：提交事务（不 commit 的话，建表操作在内存里闪一下就没了，不会落盘）
        connection.commit()
        print("核心配置表 t_streamer_config 创建/检查成功！")
        print("录播日志表 t_record_log 创建/检查成功！")

    except Exception as error:
        print(f"糟糕，连接或建表失败了。错误原因: {error}")

    finally:
        # 7. 无论成功还是报错，最后都要把连接安全关闭，释放 Mac 的内存资源
        if cursor:
            cursor.close()
        if connection:
            connection.close()
            print("数据库连接已安全关闭。")


if __name__ == "__main__":
    init_database()
