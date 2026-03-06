/**
 * Auth Controller
 * 
 * Handles user registration, login, and authentication.
 */

const User = require('../models/User');
const { generateToken } = require('../utils/jwt');
const response = require('../utils/response');

const authController = {
    /**
     * POST /api/auth/signup
     * Register a new user
     */
    async signup(req, res, next) {
        try {
            const { email, password, name } = req.body;

            // Check if email exists
            const existingUser = await User.findByEmail(email);
            if (existingUser) {
                return response.badRequest(res, 'Email already registered');
            }

            // Create user
            const user = await User.create({ email, password, name });

            // Generate token
            const token = generateToken({ userId: user.id, email: user.email });

            return response.created(res, {
                user: {
                    id: user.id,
                    email: user.email,
                    name: user.name
                },
                token
            }, 'Registration successful');

        } catch (error) {
            next(error);
        }
    },

    /**
     * POST /api/auth/login
     * Login user
     */
    async login(req, res, next) {
        try {
            const { email, password } = req.body;

            // Find user
            const user = await User.findByEmail(email);
            if (!user) {
                return response.unauthorized(res, 'Invalid email or password');
            }

            // Verify password
            const isValid = await User.verifyPassword(password, user.password);
            if (!isValid) {
                return response.unauthorized(res, 'Invalid email or password');
            }

            // Generate token
            const token = generateToken({ userId: user.id, email: user.email });

            return response.success(res, {
                user: {
                    id: user.id,
                    email: user.email,
                    name: user.name,
                    profile_picture: user.profile_picture
                },
                token
            }, 'Login successful');

        } catch (error) {
            next(error);
        }
    },

    /**
     * GET /api/auth/me
     * Get current user info
     */
    async me(req, res, next) {
        try {
            const user = await User.findById(req.user.userId);

            if (!user) {
                return response.notFound(res, 'User not found');
            }

            return response.success(res, { user });

        } catch (error) {
            next(error);
        }
    },

    /**
     * POST /api/auth/logout
     * Logout (client-side token removal, optional server tracking)
     */
    async logout(req, res, next) {
        try {
            // JWT is stateless - logout is handled client-side
            // Could add token blacklisting here if needed
            return response.success(res, null, 'Logged out successfully');
        } catch (error) {
            next(error);
        }
    }
};

module.exports = authController;
