/**
 * Input Validation Middleware
 * 
 * Uses express-validator for request validation.
 */

const { body, param, query, validationResult } = require('express-validator');
const response = require('../utils/response');

/**
 * Process validation results
 * Call this after validation rules
 */
function validate(req, res, next) {
    const errors = validationResult(req);

    if (!errors.isEmpty()) {
        const errorMessages = errors.array().map(err => ({
            field: err.path,
            message: err.msg
        }));

        return response.validationError(res, errorMessages);
    }

    next();
}

// Common validation rules
const rules = {
    // Auth validations
    email: body('email')
        .trim()
        .isEmail()
        .withMessage('Valid email required')
        .normalizeEmail(),

    password: body('password')
        .isLength({ min: 6 })
        .withMessage('Password must be at least 6 characters'),

    name: body('name')
        .trim()
        .notEmpty()
        .withMessage('Name is required')
        .isLength({ max: 100 })
        .withMessage('Name must be under 100 characters'),

    // ID param validation
    id: param('id')
        .isInt({ min: 1 })
        .withMessage('Valid ID required'),

    // Pagination
    page: query('page')
        .optional()
        .isInt({ min: 1 })
        .withMessage('Page must be positive integer'),

    limit: query('limit')
        .optional()
        .isInt({ min: 1, max: 50 })
        .withMessage('Limit must be 1-50')
};

module.exports = {
    validate,
    rules,
    body,
    param,
    query
};
