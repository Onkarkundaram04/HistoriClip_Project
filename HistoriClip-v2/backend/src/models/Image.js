/**
 * Generated Image Model
 * 
 * Database operations for generated_images table.
 */

const { query } = require('../config/database');

const Image = {
    /**
     * Create multiple images for a video
     */
    async createMany(videoId, images) {
        if (!images || images.length === 0) return [];

        const values = images.map((img, index) => [
            videoId,
            img.url,
            img.prompt || null,
            index + 1
        ]);

        const placeholders = values.map(() => '(?, ?, ?, ?)').join(', ');
        const flatValues = values.flat();

        await query(
            `INSERT INTO generated_images (video_id, image_url, prompt, order_num) 
             VALUES ${placeholders}`,
            flatValues
        );

        return true;
    },

    /**
     * Get all images for a video
     */
    async findByVideo(videoId) {
        return await query(
            'SELECT * FROM generated_images WHERE video_id = ? ORDER BY order_num',
            [videoId]
        );
    },

    /**
     * Delete images for a video
     */
    async deleteByVideo(videoId) {
        await query('DELETE FROM generated_images WHERE video_id = ?', [videoId]);
        return true;
    }
};

module.exports = Image;
