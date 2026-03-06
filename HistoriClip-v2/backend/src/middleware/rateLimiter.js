/**
 * Rate Limiter Middleware
 * 
 * Prevents abuse by limiting requests per IP.
 */

const rateLimit = require('express-rate-limit');
const config = require('../config/env');

// General API rate limiter
const apiLimiter = rateLimit({
    windowMs: config.rateLimit.windowMs, // 15 minutes default
    max: config.rateLimit.max, // 100 requests default
    message: {
        success: false,
        message: 'Too many requests. Please try again later.'
    },
    standardHeaders: true,
    legacyHeaders: false
});

// Strict limiter for auth routes (prevent brute force)
const authLimiter = rateLimit({
    windowMs: 15 * 60 * 1000, // 15 minutes
    max: 10, // 10 attempts per 15 min
    message: {
        success: false,
        message: 'Too many login attempts. Please try again in 15 minutes.'
    },
    standardHeaders: true,
    legacyHeaders: false
});

// Very strict limiter for video generation (expensive operation)
const generateLimiter = rateLimit({
    windowMs: 60 * 60 * 1000, // 1 hour
    max: 1000, // Increased for development
    message: {
        success: false,
        message: 'Generation limit reached. Please try again in an hour.'
    },
    standardHeaders: true,
    legacyHeaders: false
});

module.exports = {
    apiLimiter,
    authLimiter,
    generateLimiter
};
