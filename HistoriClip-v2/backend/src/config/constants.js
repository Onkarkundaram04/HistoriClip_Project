/**
 * Application Constants
 */

module.exports = {
    // Video Status
    VIDEO_STATUS: {
        PROCESSING: 'processing',
        COMPLETED: 'completed',
        FAILED: 'failed'
    },

    // API Types (for tracking)
    API_TYPES: {
        VISION: 'vision',
        GEMINI: 'gemini',
        STABLE_DIFFUSION: 'stable_diffusion',
        TTS: 'tts'
    },

    // Allowed File Types
    ALLOWED_IMAGE_TYPES: ['image/jpeg', 'image/jpg', 'image/png', 'image/webp'],

    // Max file size (10MB)
    MAX_FILE_SIZE: 10 * 1024 * 1024,

    // Video Settings
    VIDEO_DURATION: 30, // seconds
    IMAGES_PER_VIDEO: 4,

    // Pagination Defaults
    DEFAULT_PAGE: 1,
    DEFAULT_LIMIT: 10,
    MAX_LIMIT: 50
};
