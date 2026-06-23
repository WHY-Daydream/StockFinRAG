from pymilvus import (
    connections, CollectionSchema, FieldSchema, DataType,
    Collection, utility,
)
from config import Config
from loguru import logger


def connect_milvus():
    connections.connect(alias="default", host=Config.MILVUS_HOST, port=Config.MILVUS_PORT)


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

    index_params = {"metric_type": "IP", "index_type": "IVF_FLAT", "params": {"nlist": 1024}}
    collection.create_index("embedding", index_params)
    collection.load()
    logger.info(f"Created collection: {collection_name}")
    return collection
