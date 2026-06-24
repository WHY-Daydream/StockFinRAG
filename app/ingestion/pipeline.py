from typing import List
from langchain.text_splitter import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
from loguru import logger
import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config
from db import get_mysql
from milvus_client import connect_milvus, create_collection_if_not_exists


class FinKnowledgeBuilder:

    def __init__(self):
        connect_milvus()
        self.embedder = SentenceTransformer(Config.EMBEDDING_MODEL)
        self.col_parent = create_collection_if_not_exists(
            Config.MILVUS_COLLECTION_PARENT, Config.EMBEDDING_DIM
        )
        self.col_child = create_collection_if_not_exists(
            Config.MILVUS_COLLECTION_CHILD, Config.EMBEDDING_DIM
        )

    def split_parent_child(self, text: str) -> list:
        parent_splitter = RecursiveCharacterTextSplitter(
            chunk_size=Config.PARENT_CHUNK_SIZE,
            chunk_overlap=Config.PARENT_CHUNK_OVERLAP,
            separators=["\n\n", "\n", "。", "；", "，", " ", ""],
        )
        child_splitter = RecursiveCharacterTextSplitter(
            chunk_size=Config.CHILD_CHUNK_SIZE,
            chunk_overlap=Config.CHILD_CHUNK_OVERLAP,
            separators=["\n", "。", "；", "，", " ", ""],
        )
        parents = parent_splitter.split_text(text)
        result = []
        for p_text in parents:
            children = child_splitter.split_text(p_text)
            result.append({"parent": p_text, "children": children})
        return result

    def embed_and_store(self, texts: List[str], doc_id: int, chunk_type: str, collection):
        if not texts:
            return []
        embeddings = self.embedder.encode(texts, show_progress_bar=False, normalize_embeddings=True)
        entities = [
            [emb.tolist() for emb in embeddings],
            [doc_id] * len(texts),
            list(range(len(texts))),
            [chunk_type] * len(texts),
            texts,
        ]
        insert_result = collection.insert(entities)
        collection.flush()
        return insert_result.primary_keys

    def process_unprocessed_docs(self, limit: int = 10) -> int:
        conn = get_mysql()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, title, raw_text FROM documents WHERE chunk_count=0 LIMIT %s",
                    (limit,),
                )
                docs = cur.fetchall()
            for doc in docs:
                logger.info(f"Processing doc_id={doc['id']}: {doc['title']}")
                chunks = self.split_parent_child(doc["raw_text"])
                parent_texts = [c["parent"] for c in chunks]
                child_texts = [ch for c in chunks for ch in c["children"]]
                parent_ids = self.embed_and_store(parent_texts, doc["id"], "parent", self.col_parent)
                child_ids = self.embed_and_store(child_texts, doc["id"], "child", self.col_child)
                with conn.cursor() as cur:
                    for i, (text, mid) in enumerate(zip(parent_texts, parent_ids)):
                        cur.execute(
                            "INSERT INTO chunks (doc_id, chunk_index, chunk_type, milvus_id, content, token_count) "
                            "VALUES (%s, %s, 'parent', %s, %s, %s)",
                            (doc["id"], i, str(mid), text, len(text) // 2),
                        )
                    for i, (text, mid) in enumerate(zip(child_texts, child_ids)):
                        cur.execute(
                            "INSERT INTO chunks (doc_id, chunk_index, chunk_type, milvus_id, content, token_count) "
                            "VALUES (%s, %s, 'child', %s, %s, %s)",
                            (doc["id"], i, str(mid), text, len(text) // 2),
                        )
                    cur.execute(
                        "UPDATE documents SET chunk_count=%s WHERE id=%s",
                        (len(parent_texts) + len(child_texts), doc["id"]),
                    )
                    conn.commit()
                logger.info(f"Done: {len(parent_texts)} parents + {len(child_texts)} children")
            # 标记 BM25 索引为脏，下次检索时延迟重建
            try:
                from retrieval.cache import ResultCache
                ResultCache().redis.setex("bm25:stale", 86400, "1")
                logger.info("BM25 index marked stale, will rebuild on next search")
            except Exception as e:
                logger.warning(f"BM25 stale marker failed: {e}")
            return len(docs)
        finally:
            conn.close()
