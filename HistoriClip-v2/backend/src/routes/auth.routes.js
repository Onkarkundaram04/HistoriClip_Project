/**
 * Auth Routes
 * 
 * /api/auth/*
 */

const express = require('express');
const router = express.Router();
const authController = require('../controllers/authController');
const { authenticate } = require('../middleware/auth.middleware');
const { authLimiter } = require('../middleware/rateLimiter');
const { validate, rules } = require('../middleware/validation.middleware');

// POST /api/auth/signup - Register
router.post('/signup',
    authLimiter,
    [rules.email, rules.password, rules.name, validate],
    authController.signup
);

// POST /api/auth/login - Login
router.post('/login',
    authLimiter,
    [rules.email, rules.password, validate],
    authController.login
);

// GET /api/auth/me - Current user (protected)
router.get('/me', authenticate, authController.me);

// POST /api/auth/logout - Logout (protected)
router.post('/logout', authenticate, authController.logout);

module.exports = router;
