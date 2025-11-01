-- Mieshania Telegram Bot Database Schema
CREATE DATABASE IF NOT EXISTS mieshania CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE mieshania;

CREATE TABLE IF NOT EXISTS chats (
  chat_id BIGINT PRIMARY KEY,
  random_on TINYINT DEFAULT 0,
  random_min INT DEFAULT 60,
  random_max INT DEFAULT 180,
  mode VARCHAR(10) DEFAULT 'pg13',
  air_city_on TINYINT DEFAULT 0,
  air_region_on TINYINT DEFAULT 0,
  morning_on TINYINT DEFAULT 0,
  morning_time VARCHAR(5) DEFAULT '09:00',
  quiet_start VARCHAR(5),
  quiet_end VARCHAR(5)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS jokes (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  chat_id BIGINT NULL,
  text TEXT NOT NULL,
  weight INT DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS jokes_personal (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  text TEXT NOT NULL,
  weight INT DEFAULT 1,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS joke_history (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  chat_id BIGINT NOT NULL,
  text TEXT NOT NULL,
  source ENUM('stock','user','gpt') NOT NULL DEFAULT 'stock',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX idx_chat_mode ON chats (mode);
CREATE INDEX idx_joke_chat ON jokes (chat_id);
CREATE INDEX idx_joke_hist_chat ON joke_history (chat_id);
