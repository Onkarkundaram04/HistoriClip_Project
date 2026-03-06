/**
 * Password Hashing Utilities
 * 
 * Uses bcryptjs for secure password hashing.
 */

const bcrypt = require('bcryptjs');

const SALT_ROUNDS = 10;

/**
 * Hash a password
 * @param {string} password - Plain text password
 * @returns {Promise<string>} Hashed password
 */
async function hashPassword(password) {
    return await bcrypt.hash(password, SALT_ROUNDS);
}

/**
 * Compare password with hash
 * @param {string} password - Plain text password
 * @param {string} hash - Hashed password
 * @returns {Promise<boolean>} True if match
 */
async function comparePassword(password, hash) {
    return await bcrypt.compare(password, hash);
}

module.exports = {
    hashPassword,
    comparePassword
};
