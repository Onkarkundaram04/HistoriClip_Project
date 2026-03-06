/**
 * JWT Utility Functions
 * 
 * Token generation and verification.
 */

const jwt = require('jsonwebtoken');
const config = require('../config/env');

/**
 * Generate access token
 * @param {Object} payload - Data to encode (userId, email)
 * @returns {string} JWT token
 */
function generateToken(payload) {
    return jwt.sign(payload, config.jwt.secret, {
        expiresIn: config.jwt.expiry
    });
}

/**
 * Verify and decode token
 * @param {string} token - JWT token
 * @returns {Object|null} Decoded payload or null if invalid
 */
function verifyToken(token) {
    try {
        return jwt.verify(token, config.jwt.secret);
    } catch (error) {
        return null;
    }
}

/**
 * Decode token without verification (for debugging)
 * @param {string} token - JWT token
 * @returns {Object|null} Decoded payload
 */
function decodeToken(token) {
    try {
        return jwt.decode(token);
    } catch (error) {
        return null;
    }
}

module.exports = {
    generateToken,
    verifyToken,
    decodeToken
};
