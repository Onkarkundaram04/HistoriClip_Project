/**
 * Environment Configuration
 * 
 * Centralized access to all environment variables.
 * Provides defaults for development.
 */

module.exports = {
    // Server
    nodeEnv: process.env.NODE_ENV || 'development',
    port: parseInt(process.env.PORT) || 5000,

    // Database
    db: {
        host: process.env.DB_HOST || 'localhost',
        user: process.env.DB_USER || 'root',
        password: process.env.DB_PASSWORD || '',
        name: process.env.DB_NAME || 'historiclip',
        port: parseInt(process.env.DB_PORT) || 3306
    },

    // JWT
    jwt: {
        secret: process.env.JWT_SECRET || 'dev-secret-change-in-production',
        expiry: process.env.JWT_EXPIRY || '7d'
    },

    // Python AI Service
    pythonAiUrl: process.env.PYTHON_AI_URL || 'http://localhost:5001',
    aiServiceSecret: process.env.AI_SERVICE_SECRET || '',

    // AWS S3 (optional)
    aws: {
        accessKeyId: process.env.AWS_ACCESS_KEY_ID,
        secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY,
        region: process.env.AWS_REGION || 'ap-south-1',
        bucket: process.env.AWS_S3_BUCKET || 'historiclip-videos'
    },

    // Rate Limiting
    rateLimit: {
        windowMs: parseInt(process.env.RATE_LIMIT_WINDOW_MS) || 15 * 60 * 1000, // 15 min
        max: parseInt(process.env.RATE_LIMIT_MAX) || 100
    },

    // File Upload
    upload: {
        maxFileSize: parseInt(process.env.MAX_FILE_SIZE) || 10 * 1024 * 1024, // 10MB
        uploadDir: process.env.UPLOAD_DIR || './uploads'
    }
};
