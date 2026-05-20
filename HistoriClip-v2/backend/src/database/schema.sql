-- HistoriClip v2.0 Database Schema
-- MySQL 8.0+

-- Create Database
CREATE DATABASE IF NOT EXISTS historiclip;
USE historiclip;

-- ============================================
-- Users Table
-- ============================================
CREATE TABLE users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    email VARCHAR(255) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    name VARCHAR(100) NOT NULL,
    profile_picture VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_email (email)
);

-- ============================================
-- Videos Table
-- ============================================
CREATE TABLE videos (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    landmark_name VARCHAR(255) NOT NULL,
    script TEXT NOT NULL,
    video_url VARCHAR(500),
    thumbnail_url VARCHAR(500),
    audio_url VARCHAR(500),
    original_image_url VARCHAR(500),
    is_unesco BOOLEAN DEFAULT FALSE,
    unesco_year INT,
    unesco_category VARCHAR(100),
    location VARCHAR(255),
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    duration INT COMMENT 'Duration in seconds',
    status ENUM('processing', 'completed', 'failed') DEFAULT 'processing',
    error_message TEXT,
    processing_step VARCHAR(50) COMMENT 'Current pipeline step (vision, script, images, audio, video, xai, complete)',
    xai_matches_url VARCHAR(500) COMMENT 'URL to LightGlue keypoint match visualization',
    xai_attention_url VARCHAR(500) COMMENT 'URL to DINOv2 attention heatmap visualization',
    xai_top_matches TEXT COMMENT 'JSON array of FAISS top-K retrieval results',
    xai_tier_used VARCHAR(50) COMMENT 'Which identification tier was used (tier1_landmark, tier2_gps, tier3_*)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id),
    INDEX idx_status (status),
    INDEX idx_created_at (created_at)
);

-- ============================================
-- Generated Images Table
-- ============================================
CREATE TABLE generated_images (
    id INT PRIMARY KEY AUTO_INCREMENT,
    video_id INT NOT NULL,
    image_url VARCHAR(500) NOT NULL,
    prompt TEXT,
    order_num INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
    INDEX idx_video_id (video_id)
);

-- ============================================
-- API Usage Tracking Table
-- ============================================
CREATE TABLE api_usage (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    video_id INT,
    api_type ENUM('vision', 'gemini', 'stable_diffusion', 'tts') NOT NULL,
    tokens_used INT DEFAULT 0,
    cost DECIMAL(10, 4) DEFAULT 0.0000,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE SET NULL,
    INDEX idx_user_id (user_id),
    INDEX idx_api_type (api_type),
    INDEX idx_timestamp (timestamp)
);

-- ============================================
-- Video Shares Table (Future Feature)
-- ============================================
CREATE TABLE video_shares (
    id INT PRIMARY KEY AUTO_INCREMENT,
    video_id INT NOT NULL,
    share_token VARCHAR(100) UNIQUE NOT NULL,
    is_public BOOLEAN DEFAULT FALSE,
    views INT DEFAULT 0,
    expires_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
    INDEX idx_share_token (share_token),
    INDEX idx_video_id (video_id)
);

-- ============================================
-- Refresh Tokens Table (For JWT Refresh)
-- ============================================
CREATE TABLE refresh_tokens (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    token VARCHAR(500) NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id),
    INDEX idx_token (token(255))
);
