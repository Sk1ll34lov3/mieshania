import pymysql
from config import DB_HOST, DB_NAME, DB_USER, DB_PASS

def db():
    return pymysql.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASS,
        database=DB_NAME, autocommit=True, charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor
    )


def _column_exists(cur, table_name: str, column_name: str) -> bool:
    cur.execute(
        """
        SELECT 1
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND COLUMN_NAME = %s
        LIMIT 1
        """,
        (DB_NAME, table_name, column_name),
    )
    return bool(cur.fetchone())

def ensure_schema():
    with db() as conn, conn.cursor() as cur:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS chats (
          chat_id BIGINT PRIMARY KEY,
          random_on TINYINT NOT NULL DEFAULT 0,
          random_min INT NOT NULL DEFAULT 60,
          random_max INT NOT NULL DEFAULT 180,
          mode VARCHAR(10) NOT NULL DEFAULT 'pg13',
          chatter_on TINYINT NOT NULL DEFAULT 0,
          chatter_intensity INT NOT NULL DEFAULT 20,
          quiet_start VARCHAR(5) NULL,
          quiet_end   VARCHAR(5) NULL,
          morning_on  TINYINT NOT NULL DEFAULT 0,
          morning_time VARCHAR(5) NOT NULL DEFAULT '09:00',
          air_city_on TINYINT NOT NULL DEFAULT 0,
          air_region_on TINYINT NOT NULL DEFAULT 0
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""")
        if not _column_exists(cur, "chats", "chatter_on"):
            cur.execute("""
            ALTER TABLE chats
              ADD COLUMN chatter_on TINYINT NOT NULL DEFAULT 0
              AFTER mode
            """)
        if not _column_exists(cur, "chats", "chatter_intensity"):
            cur.execute("""
            ALTER TABLE chats
              ADD COLUMN chatter_intensity INT NOT NULL DEFAULT 20
              AFTER chatter_on
            """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS jokes (
          id INT AUTO_INCREMENT PRIMARY KEY,
          chat_id BIGINT NULL,
          text TEXT NOT NULL,
          tag VARCHAR(50) NULL,
          weight INT NOT NULL DEFAULT 1,
          KEY ix_chat (chat_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS titles (
          chat_id BIGINT NOT NULL PRIMARY KEY,
          user_id BIGINT NULL,
          username VARCHAR(255) NULL,
          title VARCHAR(255) NOT NULL,
          set_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS user_moderation (
          chat_id BIGINT NOT NULL,
          user_id BIGINT NOT NULL,
          warns INT NOT NULL DEFAULT 0,
          muted_until TIMESTAMP NULL,
          notes TEXT NULL,
          PRIMARY KEY (chat_id, user_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS user_map (
          chat_id    BIGINT NOT NULL,
          user_id    BIGINT NOT NULL,
          username   VARCHAR(255) NULL,
          first_seen TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
          last_seen  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          PRIMARY KEY (chat_id, user_id),
          KEY ix_chat_username (chat_id, username)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""")
