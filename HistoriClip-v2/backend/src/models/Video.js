/**
 * Video Model
 * 
 * Database operations for videos table.
 */

const { query, getConnection } = require('../config/database');
const { VIDEO_STATUS } = require('../config/constants');

const Video = {
    /**
     * Create a new video record
     */
    async create(videoData) {
        const {
            user_id,
            landmark_name,
            script,
            video_url = null,
            thumbnail_url = null,
            audio_url = null,
            original_image_url = null,
            is_unesco = false,
            unesco_year = null,
            unesco_category = null,
            location = null,
            latitude = null,
            longitude = null,
            duration = null,
            status = VIDEO_STATUS.PROCESSING
        } = videoData;

        const result = await query(
            `INSERT INTO videos 
            (user_id, landmark_name, script, video_url, thumbnail_url, audio_url, 
             original_image_url, is_unesco, unesco_year, unesco_category, 
             location, latitude, longitude, duration, status) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
            [user_id, landmark_name, script, video_url, thumbnail_url, audio_url,
                original_image_url, is_unesco, unesco_year, unesco_category,
                location, latitude, longitude, duration, status]
        );

        return { id: result.insertId, ...videoData };
    },

    /**
     * Find video by ID
     */
    async findById(id) {
        const rows = await query(
            'SELECT * FROM videos WHERE id = ?',
            [id]
        );
        return rows[0] || null;
    },

    /**
     * Find video by ID and user (ownership check)
     */
    async findByIdAndUser(id, userId) {
        const rows = await query(
            'SELECT * FROM videos WHERE id = ? AND user_id = ?',
            [id, userId]
        );
        return rows[0] || null;
    },

    /**
     * Get all videos for a user (with pagination)
     */
    async findByUser(userId, { page = 1, limit = 10, search = '', status = 'all' } = {}) {
        const limitNum = parseInt(limit) || 10;
        const pageNum = parseInt(page) || 1;
        const offset = (pageNum - 1) * limitNum;

        const normalizedSearch = typeof search === 'string' ? search.trim().toLowerCase() : '';
        const allowedStatuses = ['completed', 'processing', 'failed'];
        const normalizedStatus = allowedStatuses.includes(status) ? status : 'all';

        const whereClauses = ['user_id = ?'];
        const whereValues = [userId];

        if (normalizedStatus !== 'all') {
            whereClauses.push('status = ?');
            whereValues.push(normalizedStatus);
        }

        if (normalizedSearch) {
            whereClauses.push('(LOWER(COALESCE(landmark_name, \"\")) LIKE ? OR LOWER(COALESCE(location, \"\")) LIKE ?)');
            const searchPattern = `%${normalizedSearch}%`;
            whereValues.push(searchPattern, searchPattern);
        }

        const whereSql = `WHERE ${whereClauses.join(' AND ')}`;

        // Use parameterized LIMIT/OFFSET with explicit integer casting for MySQL compatibility
        const videos = await query(
            `SELECT * FROM videos 
            ${whereSql}
            ORDER BY created_at DESC 
            LIMIT ? OFFSET ?`,
            [...whereValues, limitNum, offset]
        );

        const [countResult] = await query(
            `SELECT COUNT(*) as total FROM videos ${whereSql}`,
            whereValues
        );

        const total = countResult.total || 0;
        const totalPages = Math.max(1, Math.ceil(total / limitNum));

        return {
            videos,
            total,
            page: pageNum,
            limit: limitNum,
            totalPages
        };
    },

    /**
     * Update video
     */
    async update(id, updateData) {
        const fields = [];
        const values = [];

        Object.entries(updateData).forEach(([key, value]) => {
            if (value !== undefined) {
                fields.push(`${key} = ?`);
                values.push(value);
            }
        });

        if (fields.length === 0) return false;

        values.push(id);
        await query(
            `UPDATE videos SET ${fields.join(', ')} WHERE id = ?`,
            values
        );

        return true;
    },

    /**
     * Update video status
     */
    async updateStatus(id, status, errorMessage = null) {
        await query(
            'UPDATE videos SET status = ?, error_message = ? WHERE id = ?',
            [status, errorMessage, id]
        );
        return true;
    },

    /**
     * Delete video
     */
    async delete(id) {
        await query('DELETE FROM videos WHERE id = ?', [id]);
        return true;
    },

    /**
     * Get user stats
     */
    async getUserStats(userId) {
        const [stats] = await query(
            `SELECT 
                COUNT(*) as total_videos,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status = 'processing' THEN 1 ELSE 0 END) as processing,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                SUM(CASE WHEN is_unesco = 1 THEN 1 ELSE 0 END) as unesco_sites
             FROM videos WHERE user_id = ?`,
            [userId]
        );
        return stats;
    }
};

module.exports = Video;
