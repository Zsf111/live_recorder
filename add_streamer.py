import psycopg2


def add_test_streamers():

    connection = None
    cursor = None

    try:
        connection = psycopg2.connect(
            host="localhost",
            port="5432",
            database="live_recorder",
            user="postgres",
            password="zsf3010ghdej",
        )
        cursor = connection.cursor()

        # 编写插入数据的 SQL 语句
        # EXCLUDED.streamer_name 意思是如果房间号已存在，就更新主播名字，防止报错
        insert_query = """
        INSERT INTO t_streamer_config (room_id, streamer_name, platform, is_monitored)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (room_id)
        DO UPDATE SET streamer_name = EXCLUDED.streamer_name;
        """

        # 这里填入你想测试的主播信息（这里以 Twitch 上的某个热门频道为例，你可以改成你想抓的）
        # 参数含义: (房间号/URL后缀, 主播昵称, 平台, 是否开启监控)
        test_data = [
            ("11899478", "OLDnannan", "bilibili", True),
        ]

        for streamer in test_data:
            cursor.execute(insert_query, streamer)

        connection.commit()
        print("成功往数据库注入了测试主播配置数据！")

    except Exception as error:
        print(f"注入数据失败: {error}")
    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None:
            connection.close()
            print("数据库连接已安全关闭。")


if __name__ == "__main__":
    add_test_streamers()
