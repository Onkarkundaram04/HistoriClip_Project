/**
 * Authentication Middleware
 * 
 * Verifies JWT token from Authorization header.
 * Attaches decoded user to req.user
 */

const { verifyToken } = require('../utils/jwt');
const response = require('../utils/response');

/**
 * Require authentication - blocks if no valid token
 */
function authenticate(req, res, next) {
    // Get token from header
    const authHeader = req.headers['authorization'];
    const token = authHeader && authHeader.split(' ')[1]; // Bearer TOKEN

    if (!token) {
        return response.unauthorized(res, 'Access token required');
    }

    // Verify token
    const decoded = verifyToken(token);

    if (!decoded) {
        return response.unauthorized(res, 'Invalid or expired token');
    }

    // Attach user to request
    req.user = decoded;
    next();
}

/**
 * Optional authentication - continues even without token
 * Use for routes that work with or without auth
 */
function optionalAuth(req, res, next) {
    const authHeader = req.headers['authorization'];
    const token = authHeader && authHeader.split(' ')[1];

    if (token) {
        const decoded = verifyToken(token);
        if (decoded) {
            req.user = decoded;
        }
    }

    next();
}

module.exports = {
    authenticate,
    optionalAuth
};
