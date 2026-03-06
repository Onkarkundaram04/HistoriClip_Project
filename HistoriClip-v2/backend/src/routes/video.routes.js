/**
 * Video Routes
 * 
 * /api/videos/*
 * All routes require authentication
 */

const express = require('express');
const router = express.Router();
const videoController = require('../controllers/videoController');
const { authenticate } = require('../middleware/auth.middleware');
const { validate, rules } = require('../middleware/validation.middleware');

// All video routes require authentication
router.use(authenticate);

// GET /api/videos - Get all user videos
router.get('/',
    [rules.page, rules.limit, validate],
    videoController.getAll
);

// GET /api/videos/stats - Get video statistics
router.get('/stats', videoController.getStats);

// GET /api/videos/:id - Get single video
router.get('/:id',
    [rules.id, validate],
    videoController.getOne
);

// DELETE /api/videos/:id - Delete video
router.delete('/:id',
    [rules.id, validate],
    videoController.delete
);

module.exports = router;
