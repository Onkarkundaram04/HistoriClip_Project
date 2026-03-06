/**
 * Standardized API Response Helpers
 * 
 * Consistent response format across all endpoints.
 */

/**
 * Success response
 */
function success(res, data = null, message = 'Success', statusCode = 200) {
    return res.status(statusCode).json({
        success: true,
        message,
        data
    });
}

/**
 * Created response (201)
 */
function created(res, data = null, message = 'Created successfully') {
    return success(res, data, message, 201);
}

/**
 * Error response
 */
function error(res, message = 'Something went wrong', statusCode = 500, errors = null) {
    const response = {
        success: false,
        message
    };

    if (errors) {
        response.errors = errors;
    }

    return res.status(statusCode).json(response);
}

/**
 * Bad request (400)
 */
function badRequest(res, message = 'Bad request', errors = null) {
    return error(res, message, 400, errors);
}

/**
 * Unauthorized (401)
 */
function unauthorized(res, message = 'Unauthorized') {
    return error(res, message, 401);
}

/**
 * Forbidden (403)
 */
function forbidden(res, message = 'Forbidden') {
    return error(res, message, 403);
}

/**
 * Not found (404)
 */
function notFound(res, message = 'Resource not found') {
    return error(res, message, 404);
}

/**
 * Validation error (422)
 */
function validationError(res, errors) {
    return error(res, 'Validation failed', 422, errors);
}

module.exports = {
    success,
    created,
    error,
    badRequest,
    unauthorized,
    forbidden,
    notFound,
    validationError
};
