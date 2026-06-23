import pymysql
import redis
from config import Config

_pool = None


def get_mysql():
    global _pool
    if _pool is None:
        _pool = pymysql.ConnectionPool(
            host=Config.MYSQL_HOST,
            port=Config.MYSQL_PORT,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DATABASE,
            charset="utf8mb4",
            maxconnections=10,
            cursorclass=pymysql.cursors.DictCursor,
        )
    return _pool.get_connection()


def get_redis():
    return redis.Redis(
        host=Config.REDIS_HOST,
        port=Config.REDIS_PORT,
        db=Config.REDIS_DB,
        decode_responses=True,
    )
