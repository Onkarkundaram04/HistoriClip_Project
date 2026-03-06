/**
 * User Routes
 * 
 * /api/user/*
 * All routes require authentication
 */

const express = require('express');
const router = express.Router();
const userController = require('../controllers/userController');
const { authenticate } = require('../middleware/auth.middleware');
const { validate, body } = require('../middleware/validation.middleware');

// All user routes require authentication
router.use(authenticate);

// GET /api/user/profile - Get profile
router.get('/profile', userController.getProfile);

// PATCH /api/user/profile - Update profile
router.patch('/profile',
    [
        body('name').optional().trim().isLength({ max: 100 }),
        body('profile_picture').optional().isURL(),
        validate
    ],
    userController.updateProfile
);

// GET /api/user/stats - Get statistics
router.get('/stats', userController.getStats);

module.exports = router;
