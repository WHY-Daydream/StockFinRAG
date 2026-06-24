"""
一键清理旧数据 + 重建向量库

用法:
    cd StockFinRAG && python scripts/reset_and_build.py

操作:
    1. 删掉 MySQL 中的爬虫垃圾数据（ID 1,2,3,12,13,14,15）
    2. 删掉 Milvus 旧集合
    3. 设置种子文档 chunk_count=0
    4. 建 stock_indices 表
    5. 告诉你怎么启动服务
"""
import sys, os

# 设置项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "app"))
os.environ["HF_HOME"] = os.path.join(PROJECT_ROOT, "models", "huggingface")
os.environ["HF_HUB_CACHE"] = os.path.join(PROJECT_ROOT, "models", "huggingface", "hub")

print("=" * 50)
print("StockFinRAG 一键清理与重建")
print("=" * 50)

# 1. 清理 MySQL 旧数据
print("\n[1/4] 清理 MySQL 旧数据...")
BAD_IDS = [1, 2, 3, 12, 13, 14, 15]
from db import get_mysql
conn = get_mysql()
try:
    with conn.cursor() as cur:
        placeholders = ",".join(["%s"] * len(BAD_IDS))
        cur.execute(f"DELETE FROM chunks WHERE doc_id IN ({placeholders})", BAD_IDS)
        print(f"  删除了 {cur.rowcount} 条垃圾 chunk")
        cur.execute(f"DELETE FROM documents WHERE id IN ({placeholders})", BAD_IDS)
        print(f"  删除了 {cur.rowcount} 条垃圾文档")
        cur.execute("UPDATE documents SET chunk_count = 0")
        print(f"  重置了种子文档的 chunk_count")
        conn.commit()
        cur.execute("SELECT COUNT(*) as cnt FROM documents")
        print(f"  剩余文档: {cur.fetchone()['cnt']} 篇")
finally:
    conn.close()

# 2. 删除 Milvus 旧集合
print("\n[2/4] 删除 Milvus 旧集合...")
from pymilvus import utility
from config import Config
from milvus_client import connect_milvus
connect_milvus()
for name in [Config.MILVUS_COLLECTION_PARENT, Config.MILVUS_COLLECTION_CHILD]:
    if utility.has_collection(name):
        utility.drop_collection(name)
        print(f"  已删除: {name}")

# 3. 创建 stock_indices 表
print("\n[3/4] 创建 stock_indices 表...")
try:
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS stock_indices (
                id          BIGINT AUTO_INCREMENT PRIMARY KEY,
                index_code  VARCHAR(16) NOT NULL COMMENT '指数代码',
                index_name  VARCHAR(32) NOT NULL,
                date        DATE NOT NULL,
                open        DECIMAL(12,2),
                close       DECIMAL(12,2),
                high        DECIMAL(12,2),
                low         DECIMAL(12,2),
                volume      BIGINT,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uk_index_date (index_code, date)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        conn.commit()
        print("  stock_indices 表已就绪")
finally:
    conn.close()

# 4. 完成
print("\n" + "=" * 50)
print("✅ 清理完成！接下来：")
print("=" * 50)
print("""
  1. 启动 API 服务:
     cd app && python api_server.py

  2. 新开终端，导入种子数据并向量化:
     curl -X POST http://127.0.0.1:5000/api/seed

  3. 打开浏览器访问 http://127.0.0.1:5000

  4. 测试提问:
     curl -s -X POST http://127.0.0.1:5000/api/ask \\
       -H "Content-Type: application/json" \\
       -d '{"question":"什么是金融合规？"}' | python -m json.tool
""")
