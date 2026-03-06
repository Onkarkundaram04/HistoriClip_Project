/**
 * User Controller
 * 
 * Handles user profile operations.
 */

const User = require('../models/User');
const Video = require('../models/Video');
const response = require('../utils/response');

const userController = {
    /**
     * GET /api/user/profile
     * Get current user profile
     */
    async getProfile(req, res, next) {
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
     * PATCH /api/user/profile
     * Update user profile
     */
    async updateProfile(req, res, next) {
        try {
            const { name, profile_picture } = req.body;

            if (!name && !profile_picture) {
                return response.badRequest(res, 'Nothing to update');
            }

            await User.update(req.user.userId, { name, profile_picture });

            const user = await User.findById(req.user.userId);

            return response.success(res, { user }, 'Profile updated');

        } catch (error) {
            next(error);
        }
    },

    /**
     * GET /api/user/stats
     * Get user statistics
     */
    async getStats(req, res, next) {
        try {
            const videoStats = await Video.getUserStats(req.user.userId);

            return response.success(res, {
                videos: videoStats
            });

        } catch (error) {
            next(error);
        }
    }
};

module.exports = userController;
