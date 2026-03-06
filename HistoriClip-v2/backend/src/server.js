/**
 * HistoriClip - Backend Server Entry Point
 * 
 * Express.js server with JWT authentication, MySQL database,
 * and connection to Python AI microservice.
 */

require('dotenv').config({ path: require('path').resolve(__dirname, '../../.env') });

const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const morgan = require('morgan');
const path = require('path');
const fs = require('fs');

// Import routes
const routes = require('./routes');

// Import middleware
const errorHandler = require('./middleware/errorHandler');

// Import config
const { connectDatabase } = require('./config/database');

// Initialize Express app
const app = express();

// ===========================================
// Middleware Configuration
// ===========================================

// Security headers — configured for development cross-origin access
// Default helmet() sets Cross-Origin-Resource-Policy: same-origin which
// blocks video/audio/image files from loading on the frontend (different port)
app.use(helmet({
    crossOriginResourcePolicy: { policy: 'cross-origin' },
    contentSecurityPolicy: false  // Disable CSP in dev (frontend is on different port)
}));

// CORS configuration
// In development: allow localhost origins
// In production: restrict to specific origins or same-origin via nginx
const corsOrigin = process.env.CORS_ORIGIN || 'http://localhost:80,http://localhost:5000,http://localhost:5500,http://localhost:8000,http://localhost:5173,http://localhost:4173';
const configuredOrigins = corsOrigin
    .split(',')
    .map((origin) => origin.trim())
    .filter(Boolean);

app.use(cors({
    origin: (origin, callback) => {
        if (!origin) {
            return callback(null, true);
        }

        const isConfigured = configuredOrigins.includes(origin);
        const isLocalhostLike = /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/i.test(origin);
        const isPrivateLan = /^https?:\/\/(192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3})(:\d+)?$/i.test(origin);

        if (isConfigured || isLocalhostLike || isPrivateLan) {
            return callback(null, true);
        }

        return callback(new Error(`CORS blocked for origin: ${origin}`));
    },
    methods: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'],
    allowedHeaders: ['Content-Type', 'Authorization', 'X-AI-Service-Secret'],
    credentials: true
}));

// Request logging
app.use(morgan('dev'));

// Body parsers
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true, limit: '10mb' }));

// Dedicated download route (bypasses express.static's inline display)
app.get('/download', (req, res) => {
    let fileUrl = req.query.url;
    if (!fileUrl) return res.status(400).send('No file URL specified');
    try {
        // Only extract the path part if it's a full URL
        let urlPath;
        if (fileUrl.startsWith('http')) {
            urlPath = new URL(fileUrl).pathname;
        } else {
            urlPath = fileUrl;
        }

        // Must be in the uploads directory
        if (!urlPath.startsWith('/uploads/')) {
            return res.status(403).send('Invalid file path');
        }

        const relativePath = urlPath.replace('/uploads/', '');
        const absolutePath = path.join(__dirname, '../uploads', relativePath);

        // res.download forces the browser's "Save As" dialogue
        res.download(absolutePath, 'HistoriClip_Video.mp4', (err) => {
            if (err) {
                console.error('Download error:', err);
                if (!res.headersSent) res.status(404).send('File not found');
            }
        });
    } catch (e) {
        res.status(400).send('Invalid request');
    }
});

// Static files (for inline viewing/playing in browser)
app.use('/uploads', express.static(path.join(__dirname, '../uploads')));

// ===========================================
// API Routes
// ===========================================

// Health check endpoint
app.get('/api/health', (req, res) => {
    res.json({
        status: 'ok',
        message: 'HistoriClip API is running',
        timestamp: new Date().toISOString(),
        version: '2.0.0'
    });
});

// Mount all routes
app.use('/api', routes);

// Serve React frontend build if available (production-friendly)
const reactDistPath = path.resolve(__dirname, '../../frontend-react/dist');
if (fs.existsSync(reactDistPath)) {
    app.use(express.static(reactDistPath));

    app.get('*', (req, res, next) => {
        if (req.path.startsWith('/api') || req.path.startsWith('/uploads') || req.path.startsWith('/download')) {
            return next();
        }

        return res.sendFile(path.join(reactDistPath, 'index.html'));
    });
}

// ===========================================
// Error Handling
// ===========================================

// 404 handler
app.use((req, res) => {
    res.status(404).json({
        success: false,
        error: 'Endpoint not found'
    });
});

// Global error handler
app.use(errorHandler);

// ===========================================
// Server Initialization
// ===========================================

const PORT = process.env.PORT || 5000;

async function startServer() {
    try {
        // Connect to database
        await connectDatabase();
        console.log('✅ Database connected successfully');

        // Start server
        app.listen(PORT, () => {
            console.log(`\n🚀 HistoriClip Backend Server`);
            console.log(`📍 Environment: ${process.env.NODE_ENV || 'development'}`);
            console.log(`🌐 Server running on: http://localhost:${PORT}`);
            console.log(`📡 API Base URL: http://localhost:${PORT}/api`);
            console.log(`💚 Health Check: http://localhost:${PORT}/api/health\n`);
        });
    } catch (error) {
        console.error('❌ Failed to start server:', error.message);
        process.exit(1);
    }
}

// Handle unhandled promise rejections
process.on('unhandledRejection', (err) => {
    console.error('Unhandled Promise Rejection:', err);
    process.exit(1);
});

// Handle uncaught exceptions
process.on('uncaughtException', (err) => {
    console.error('Uncaught Exception:', err);
    process.exit(1);
});

// Start the server
startServer();

module.exports = app;
