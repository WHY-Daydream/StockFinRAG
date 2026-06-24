import pymysql
from dbutils.pooled_db import PooledDB
import redis
from threading import Lock
from config import Config

_pool = None
_lock = Lock()


def get_mysql():
    global _pool
    with _lock:
        if _pool is None:
            _pool = PooledDB(
                creator=pymysql,
                mincached=1,
                maxcached=10,
                maxconnections=10,
                blocking=True,
                ping=1,
                host=Config.MYSQL_HOST,
                port=Config.MYSQL_PORT,
                user=Config.MYSQL_USER,
                password=Config.MYSQL_PASSWORD,
                database=Config.MYSQL_DATABASE,
                charset="utf8mb4",
                cursorclass=pymysql.cursors.DictCursor,
            )
    return _pool.connection()


def get_redis():
    return redis.Redis(
        host=Config.REDIS_HOST,
        port=Config.REDIS_PORT,
        password=Config.REDIS_PASSWORD,
        db=Config.REDIS_DB,
        decode_responses=True,
    )
