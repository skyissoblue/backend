CREATE TABLE IF NOT EXISTS users (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  phone VARCHAR(20) UNIQUE NOT NULL,
  nickname VARCHAR(50) NULL,
  password_hash VARCHAR(255) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_phone (phone)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS selection_combos (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id BIGINT NOT NULL,
  name VARCHAR(100) NOT NULL,
  asset_type VARCHAR(8) NOT NULL DEFAULT 'stock',
  conditions_json JSON NOT NULL,
  result_codes JSON NOT NULL,
  result_count INT NOT NULL DEFAULT 0,
  is_favorite TINYINT NOT NULL DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  INDEX idx_combo_user (user_id),
  INDEX idx_combo_asset_type (user_id,asset_type),
  INDEX idx_combo_favorite (user_id,is_favorite)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS watchlist (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id BIGINT NOT NULL,
  stock_code VARCHAR(10) NOT NULL,
  stock_name VARCHAR(64) NULL,
  source_combo_id BIGINT NULL,
  source_combo_name VARCHAR(100) NULL,
  note VARCHAR(200) NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  UNIQUE KEY uk_watchlist_user_stock (user_id,stock_code),
  INDEX idx_watchlist_source (source_combo_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS stocks (
  code VARCHAR(10) PRIMARY KEY,
  name VARCHAR(64) NOT NULL,
  industry VARCHAR(64) NULL,
  board VARCHAR(16) NULL,
  close DOUBLE NULL,
  daily_ma5 DOUBLE NULL,
  daily_ma10 DOUBLE NULL,
  daily_ma20 DOUBLE NULL,
  daily_ma60 DOUBLE NULL,
  daily_ma120 DOUBLE NULL,
  daily_ma250 DOUBLE NULL,
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
