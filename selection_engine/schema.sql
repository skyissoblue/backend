CREATE TABLE IF NOT EXISTS stocks (
  code VARCHAR(10) PRIMARY KEY,
  name VARCHAR(64) NOT NULL,
  industry VARCHAR(64) NULL,
  board VARCHAR(16) NULL,
  close DOUBLE NULL,
  weekly_ma10 DOUBLE NULL,
  weekly_deviation DOUBLE NULL,
  rps_250 DOUBLE NULL,
  volume_ratio DOUBLE NULL,
  market_cap BIGINT NULL,
  pe DOUBLE NULL,
  listed_days INT NULL,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_industry (industry),
  INDEX idx_board (board),
  INDEX idx_market_cap (market_cap)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS update_log (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  status VARCHAR(16) NOT NULL,
  details_json JSON NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
