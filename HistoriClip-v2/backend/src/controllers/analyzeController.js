/**
 * Analyze Controller
 * 
 * Handles image upload and video generation pipeline.
 * Communicates with Python AI service.
 */

const axios = require('axios');
const Video = require('../models/Video');
const Image = require('../models/Image');
const response = require('../utils/response');
const config = require('../config/env');
const { VIDEO_STATUS } = require('../config/constants');
const FormData = require('form-data');
const fs = require('fs');
const path = require('path');

const analyzeController = {
    /**
     * POST /api/analyze
     * Upload image and generate documentary video
     */
    async generate(req, res, next) {
        let videoId = null;

        try {
            // Check if file uploaded
            if (!req.file) {
                return response.badRequest(res, 'Image file required');
            }

            const imagePath = req.file.path;
            const imageUrl = `/uploads/${req.file.filename}`;

            // Create initial video record (processing status)
            const videoRecord = await Video.create({
                user_id: req.user.userId,
                landmark_name: 'Processing...',
                script: '',
                original_image_url: imageUrl,
                status: VIDEO_STATUS.PROCESSING
            });

            videoId = videoRecord.id;

            const duration = req.body.duration || 'normal';
            console.log(`[Analyze] Starting background video generation for ID: ${videoId}, Duration: ${duration}`);

            // Start background processing without awaiting
            analyzeController.processVideoGenerationBackground(videoId, imagePath, duration).catch(err => {
                console.error('[Background Gen Error]', err);
            });

            // Return early response to start polling
            return response.success(res, {
                id: videoId,
                status: VIDEO_STATUS.PROCESSING,
                message: 'Video generation started in background'
            }, 'Video generation started successfully');

        } catch (error) {
            next(error);
        }
    },

    /**
     * Background task for communicating with Python AI service
     */
    async processVideoGenerationBackground(videoId, imagePath, duration) {
        try {
            // Send to Python AI service
            const formData = new FormData();
            formData.append('image', fs.createReadStream(imagePath));
            formData.append('speed', duration);
            formData.append('video_id', String(videoId));
            formData.append('callback_url', `http://localhost:${config.port}/api/analyze/progress`);

            console.log(`[Background] Sending request to Python AI Service for Video ID: ${videoId}`);

            // First, quick connectivity check
            try {
                await axios.get(`${config.pythonAiUrl}/health`, { timeout: 5000 });
                console.log('[Background] Python AI service is healthy');
            } catch (healthError) {
                throw new Error('AI service unavailable. Please ensure Python AI Service is running on port 5001.');
            }

            const aiResponse = await axios.post(
                `${config.pythonAiUrl}/generate`,
                formData,
                {
                    headers: {
                        ...formData.getHeaders(),
                        'X-AI-Service-Secret': config.aiServiceSecret
                    },
                    timeout: 2400000 // Extended timeout (40 mins) for heavy SDXL generation
                }
            );

            const result = aiResponse.data;

            if (!result.success) {
                throw new Error(result.error || 'AI processing failed');
            }

            console.log(`[Background] Received successful response for Video ID: ${videoId}`);

            // Convert location object to string for database storage
            let locationStr = null;
            if (result.location) {
                if (typeof result.location === 'object') {
                    locationStr = result.location.name || result.location.display_name ||
                        `${result.location.city || ''}, ${result.location.country || ''}`.trim();
                } else {
                    locationStr = result.location;
                }
            }

            // Update video record with results
            await Video.update(videoId, {
                landmark_name: result.landmark,
                script: result.script,
                video_url: result.video_path,
                audio_url: result.audio_path,
                is_unesco: result.is_unesco || false,
                unesco_year: result.unesco_year,
                location: locationStr,
                latitude: result.gps?.lat,
                longitude: result.gps?.lon,
                xai_matches_url: result.xai_matches_url || null,
                xai_attention_url: result.xai_attention_url || null,
                xai_top_matches: result.xai_top_matches ? JSON.stringify(result.xai_top_matches) : null,
                xai_tier_used: result.xai_tier_used || null,
                status: VIDEO_STATUS.COMPLETED
            });

            // Save generated images
            if (result.image_paths && result.image_paths.length > 0) {
                const images = result.image_paths.map((url, index) => ({
                    url,
                    prompt: result.prompts?.[index] || null
                }));
                await Image.createMany(videoId, images);
            }

            console.log(`[Background] Successfully completed generation for Video ID: ${videoId}`);

        } catch (error) {
            console.error(`[Background Error] Video ID: ${videoId} failed. Reason:`, error.message);
            // Update video status to failed
            let errorMessage = error.message;
            if (error.code === 'ECONNREFUSED' || error.code === 'ECONNRESET') {
                errorMessage = 'AI service connection lost. Please check if Python AI Service is running and try again.';
            } else if (error.response?.data?.error) {
                errorMessage = error.response.data.error;
            }

            if (videoId) {
                await Video.updateStatus(videoId, VIDEO_STATUS.FAILED, errorMessage);
            }
        }
    },

    /**
     * POST /api/analyze/vision
     * Only analyze image (without full video generation)
     */
    async analyzeOnly(req, res, next) {
        try {
            if (!req.file) {
                return response.badRequest(res, 'Image file required');
            }

            const formData = new FormData();
            formData.append('image', fs.createReadStream(req.file.path));

            const aiResponse = await axios.post(
                `${config.pythonAiUrl}/analyze/vision`,
                formData,
                {
                    headers: {
                        ...formData.getHeaders(),
                        'X-AI-Service-Secret': config.aiServiceSecret
                    },
                    timeout: 30000
                }
            );

            return response.success(res, aiResponse.data);

        } catch (error) {
            if (error.code === 'ECONNREFUSED') {
                return response.error(res, 'AI service unavailable', 503);
            }
            next(error);
        }
    },

    /**
     * POST /api/analyze/progress
     * Internal endpoint for Python AI service to report step progress
     */
    async updateProgress(req, res) {
        try {
            const { video_id, step } = req.body;
            if (!video_id || !step) {
                return res.status(400).json({ error: 'video_id and step required' });
            }
            await Video.update(video_id, { processing_step: step });
            console.log(`[Progress] Video ${video_id} → ${step}`);
            return res.json({ ok: true });
        } catch (error) {
            console.error('[Progress] Error:', error.message);
            return res.status(500).json({ error: error.message });
        }
    }
};

module.exports = analyzeController;
