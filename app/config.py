import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Milvus
    MILVUS_HOST = os.getenv("MILVUS_HOST", "127.0.0.1")
    MILVUS_PORT = int(os.getenv("MILVUS_PORT", "19530"))
    MILVUS_DATABASE = os.getenv("MILVUS_DATABASE", "default")

    # MySQL
    MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "StockFinRAG@2025")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "stock_finrag")

    # Redis
    REDIS_HOST = os.getenv("REDIS_HOST", "127.0.0.1")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
    REDIS_DB = int(os.getenv("REDIS_DB", "0"))

    # LLM
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")

    # Embedding（使用已缓存的本地模型，避免从 HuggingFace 下载）
    EMBEDDING_MODEL = "BAAI/bge-large-zh-v1.5"
    EMBEDDING_DIM = 1024

    # Milvus collections
    MILVUS_COLLECTION_PARENT = "finrag_chunk_parent"
    MILVUS_COLLECTION_CHILD = "finrag_chunk_child"

    # Chunk sizes
    PARENT_CHUNK_SIZE = 1024
    PARENT_CHUNK_OVERLAP = 128
    CHILD_CHUNK_SIZE = 256
    CHILD_CHUNK_OVERLAP = 32

    # Rerank
    RERANK_MODEL = "BAAI/bge-reranker-v2-m3"

    # Cache
    CACHE_TTL = 300
