/**
 * Video Controller
 * 
 * Handles CRUD operations for user videos.
 */

const Video = require('../models/Video');
const Image = require('../models/Image');
const response = require('../utils/response');
const fs = require('fs').promises;
const path = require('path');

const videoController = {
    /**
     * GET /api/videos
     * Get all videos for current user
     */
    async getAll(req, res, next) {
        try {
            const { page = 1, limit = 10, search = '', status = 'all' } = req.query;

            const result = await Video.findByUser(req.user.userId, {
                page: parseInt(page),
                limit: parseInt(limit),
                search,
                status
            });

            console.log(`[VideoController] getAll for user ${req.user.userId}: Found ${result.videos.length} videos (Total: ${result.total}, page: ${result.page}, status: ${status || 'all'}, search: ${search || '-'})`); // Debug log

            return response.success(res, result);

        } catch (error) {
            next(error);
        }
    },

    /**
     * GET /api/videos/:id
     * Get single video with images
     */
    async getOne(req, res, next) {
        try {
            const video = await Video.findByIdAndUser(req.params.id, req.user.userId);

            if (!video) {
                return response.notFound(res, 'Video not found');
            }

            // Get associated images
            const images = await Image.findByVideo(video.id);

            return response.success(res, {
                ...video,
                images
            });

        } catch (error) {
            next(error);
        }
    },

    /**
     * DELETE /api/videos/:id
     * Delete a video
     */
    async delete(req, res, next) {
        try {
            const video = await Video.findByIdAndUser(req.params.id, req.user.userId);

            if (!video) {
                return response.notFound(res, 'Video not found');
            }

            // Delete associated files (if stored locally)
            try {
                if (video.video_url && video.video_url.startsWith('/uploads')) {
                    await fs.unlink(path.join(__dirname, '../..', video.video_url));
                }
                if (video.audio_url && video.audio_url.startsWith('/uploads')) {
                    await fs.unlink(path.join(__dirname, '../..', video.audio_url));
                }
            } catch (fileError) {
                console.log('File cleanup error (non-critical):', fileError.message);
            }

            // Delete from database (cascades to images)
            await Video.delete(video.id);

            return response.success(res, null, 'Video deleted successfully');

        } catch (error) {
            next(error);
        }
    },

    /**
     * GET /api/videos/stats
     * Get user video statistics
     */
    async getStats(req, res, next) {
        try {
            const stats = await Video.getUserStats(req.user.userId);
            return response.success(res, stats);
        } catch (error) {
            next(error);
        }
    }
};

module.exports = videoController;
