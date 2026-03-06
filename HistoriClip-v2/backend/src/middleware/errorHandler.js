/**
 * Global Error Handler Middleware
 * 
 * Catches all errors and returns consistent response.
 */

const config = require('../config/env');

function errorHandler(err, req, res, next) {
    // Log error in development
    if (config.nodeEnv === 'development') {
        console.error('❌ Error:', err);
    }

    // Default error
    let statusCode = err.statusCode || 500;
    let message = err.message || 'Internal server error';

    // Handle specific error types
    if (err.name === 'ValidationError') {
        statusCode = 400;
        message = 'Validation failed';
    }

    if (err.name === 'JsonWebTokenError') {
        statusCode = 401;
        message = 'Invalid token';
    }

    if (err.name === 'TokenExpiredError') {
        statusCode = 401;
        message = 'Token expired';
    }

    // MySQL duplicate entry
    if (err.code === 'ER_DUP_ENTRY') {
        statusCode = 409;
        message = 'Duplicate entry';
    }

    // Response
    const response = {
        success: false,
        message
    };

    // Include stack trace in development
    if (config.nodeEnv === 'development') {
        response.stack = err.stack;
    }

    res.status(statusCode).json(response);
}

module.exports = errorHandler;
