/**
 * Analyze Routes
 * 
 * /api/analyze/*
 * Handles image upload and video generation
 */

const express = require('express');
const router = express.Router();
const analyzeController = require('../controllers/analyzeController');
const { authenticate } = require('../middleware/auth.middleware');
const { handleUpload } = require('../middleware/upload.middleware');
const { generateLimiter } = require('../middleware/rateLimiter');

// Internal endpoint — secured by AI service secret, no user auth
router.post('/progress', analyzeController.updateProgress);

// All other analyze routes require authentication
router.use(authenticate);

// POST /api/analyze - Full video generation
router.post('/',
    generateLimiter,
    handleUpload,
    analyzeController.generate
);

// POST /api/analyze/vision - Vision analysis only (testing)
router.post('/vision',
    handleUpload,
    analyzeController.analyzeOnly
);

module.exports = router;
