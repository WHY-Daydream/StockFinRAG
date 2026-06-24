CREATE TABLE IF NOT EXISTS documents (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    doc_type    VARCHAR(32)  NOT NULL COMMENT '财报/研报/政策/新闻',
    title       VARCHAR(255) NOT NULL,
    source      VARCHAR(255) DEFAULT NULL,
    author      VARCHAR(128) DEFAULT NULL,
    publish_date DATE DEFAULT NULL,
    summary     TEXT,
    raw_text    LONGTEXT,
    chunk_count INT DEFAULT 0,
    file_hash   VARCHAR(64) UNIQUE,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_doc_type (doc_type),
    INDEX idx_publish_date (publish_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS chunks (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    doc_id      BIGINT NOT NULL,
    chunk_index INT DEFAULT 0,
    chunk_type  VARCHAR(16) DEFAULT 'child' COMMENT 'parent/child',
    milvus_id   VARCHAR(64),
    content     TEXT NOT NULL,
    token_count INT DEFAULT 0,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (doc_id) REFERENCES documents(id) ON DELETE CASCADE,
    INDEX idx_doc_id (doc_id),
    INDEX idx_chunk_type (chunk_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS qa_logs (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    session_id      VARCHAR(64) NOT NULL,
    question        TEXT NOT NULL,
    answer          TEXT,
    retrieved_chunks JSON,
    agent_trace     JSON,
    compliance_check VARCHAR(32) DEFAULT 'pending',
    model_name      VARCHAR(64),
    latency_ms      INT DEFAULT 0,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_session (session_id),
    INDEX idx_compliance (compliance_check),
    INDEX idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
