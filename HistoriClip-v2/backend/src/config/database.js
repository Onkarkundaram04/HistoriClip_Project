/**
 * Database Configuration - MySQL Connection Pool
 * 
 * Uses mysql2 with promise support for async/await.
 * Connection pooling for better performance.
 */

const mysql = require('mysql2/promise');

// Create connection pool
const pool = mysql.createPool({
    host: process.env.DB_HOST || 'localhost',
    user: process.env.DB_USER || 'root',
    password: process.env.DB_PASSWORD || '',
    database: process.env.DB_NAME || 'historiclip',
    port: process.env.DB_PORT || 3306,
    waitForConnections: true,
    connectionLimit: 10,
    queueLimit: 0
});

/**
 * Test database connection
 */
async function connectDatabase() {
    try {
        const connection = await pool.getConnection();
        console.log(`📦 MySQL connected to: ${process.env.DB_NAME}`);
        connection.release();
        return true;
    } catch (error) {
        console.error('❌ Database connection failed:', error.message);
        throw error;
    }
}

/**
 * Execute a query with parameters
 * @param {string} sql - SQL query
 * @param {Array} params - Query parameters
 */
async function query(sql, params = []) {
    const [rows] = await pool.query(sql, params);
    return rows;
}

/**
 * Get a connection from pool (for transactions)
 */
async function getConnection() {
    return await pool.getConnection();
}

module.exports = {
    pool,
    connectDatabase,
    query,
    getConnection
};
