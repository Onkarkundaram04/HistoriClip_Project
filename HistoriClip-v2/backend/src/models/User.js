/**
 * User Model
 * 
 * Database operations for users table.
 */

const { query } = require('../config/database');
const { hashPassword, comparePassword } = require('../utils/bcrypt');

const User = {
    /**
     * Create a new user
     */
    async create({ email, password, name }) {
        const hashedPassword = await hashPassword(password);

        const result = await query(
            'INSERT INTO users (email, password, name) VALUES (?, ?, ?)',
            [email, hashedPassword, name]
        );

        return { id: result.insertId, email, name };
    },

    /**
     * Find user by email
     */
    async findByEmail(email) {
        const rows = await query(
            'SELECT * FROM users WHERE email = ?',
            [email]
        );
        return rows[0] || null;
    },

    /**
     * Find user by ID
     */
    async findById(id) {
        const rows = await query(
            'SELECT id, email, name, profile_picture, created_at FROM users WHERE id = ?',
            [id]
        );
        return rows[0] || null;
    },

    /**
     * Update user profile
     */
    async update(id, { name, profile_picture }) {
        const fields = [];
        const values = [];

        if (name) {
            fields.push('name = ?');
            values.push(name);
        }
        if (profile_picture) {
            fields.push('profile_picture = ?');
            values.push(profile_picture);
        }

        if (fields.length === 0) return false;

        values.push(id);
        await query(
            `UPDATE users SET ${fields.join(', ')} WHERE id = ?`,
            values
        );

        return true;
    },

    /**
     * Verify password
     */
    async verifyPassword(plainPassword, hashedPassword) {
        return await comparePassword(plainPassword, hashedPassword);
    }
};

module.exports = User;
