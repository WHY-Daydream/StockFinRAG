from pymilvus import (
    connections, CollectionSchema, FieldSchema, DataType,
    Collection, utility,
)
from config import Config
from loguru import logger


def connect_milvus():
    connections.connect(alias="default", host=Config.MILVUS_HOST, port=Config.MILVUS_PORT,
                        db_name=Config.MILVUS_DATABASE)


def create_collection_if_not_exists(collection_name: str, dim: int) -> Collection:
    if utility.has_collection(collection_name):
        col = Collection(collection_name)
        col.load()
        return col

    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim),
        FieldSchema(name="doc_id", dtype=DataType.INT64),
        FieldSchema(name="chunk_id", dtype=DataType.INT64),
        FieldSchema(name="chunk_type", dtype=DataType.VARCHAR, max_length=16),
        FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=8192),
    ]
    schema = CollectionSchema(fields, description=collection_name)
    collection = Collection(collection_name, schema)

    index_params = {"metric_type": "IP", "index_type": "FLAT", "params": {}}
    collection.create_index("embedding", index_params)
    collection.load()
    logger.info(f"Created collection: {collection_name}")
    return collection

def rebuild_index(collection_name: str):
    """重建索引（当数据量变化较大时调用）"""
    if utility.has_collection(collection_name):
        col = Collection(collection_name)
        col.release()
        col.drop_index()
        index_params = {"metric_type": "IP", "index_type": "FLAT", "params": {}}
        col.create_index("embedding", index_params)
        col.load()
        logger.info(f"Rebuilt index for {collection_name}")
