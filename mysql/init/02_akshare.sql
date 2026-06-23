-- mysql/init/02_akshare.sql
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
