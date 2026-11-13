CREATE TABLE IF NOT EXISTS pay_accounts (
 id CHAR(32) PRIMARY KEY, token_hash CHAR(64) NOT NULL UNIQUE,
 email VARCHAR(254) NOT NULL, created_at BIGINT NOT NULL,
 auto_renew TINYINT NOT NULL DEFAULT 0, consent_revision INT NOT NULL DEFAULT 0,
 method_cipher TEXT NULL, monthly_until BIGINT NOT NULL DEFAULT 0,
 permanent TINYINT NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS pay_orders (
 id CHAR(32) PRIMARY KEY, account_id CHAR(32) NOT NULL,
 request_key VARCHAR(80) NOT NULL, plan VARCHAR(32) NOT NULL,
 amount INT NOT NULL, status VARCHAR(24) NOT NULL DEFAULT 'creating',
 provider_id VARCHAR(64) NULL UNIQUE, payload_cipher TEXT NULL,
 created_at BIGINT NOT NULL, applied_at BIGINT NULL,
 grant_start BIGINT NULL, grant_end BIGINT NULL,
 consent_revision INT NOT NULL, recurring TINYINT NOT NULL DEFAULT 0,
 refunded TINYINT NOT NULL DEFAULT 0, receipt_status VARCHAR(24) NOT NULL DEFAULT 'not_due',
 UNIQUE KEY account_request(account_id,request_key),
 KEY pending_orders(status,created_at),
 FOREIGN KEY (account_id) REFERENCES pay_accounts(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS pay_rate_limits (
 bucket CHAR(64) PRIMARY KEY, hits INT NOT NULL, expires_at BIGINT NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS pay_gift_keys (
 id CHAR(32) PRIMARY KEY, key_hash CHAR(64) NOT NULL UNIQUE,
 label VARCHAR(120) NOT NULL, test_mode TINYINT NOT NULL,
 created_at BIGINT NOT NULL, redeemed_by CHAR(32) NULL,
 redeemed_at BIGINT NULL, revoked TINYINT NOT NULL DEFAULT 0,
 KEY gift_account(redeemed_by),
 FOREIGN KEY (redeemed_by) REFERENCES pay_accounts(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
