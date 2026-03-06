/**
 * Route Aggregator
 * 
 * Combines all route modules.
 * Mounted at /api in server.js
 */

const express = require('express');
const router = express.Router();

// Import route modules
const authRoutes = require('./auth.routes');
const videoRoutes = require('./video.routes');
const analyzeRoutes = require('./analyze.routes');
const userRoutes = require('./user.routes');

// Mount routes
router.use('/auth', authRoutes);
router.use('/videos', videoRoutes);
router.use('/analyze', analyzeRoutes);
router.use('/user', userRoutes);

module.exports = router;
