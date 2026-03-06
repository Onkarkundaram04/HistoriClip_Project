/**
 * File Upload Middleware
 * 
 * Handles multipart/form-data uploads using multer.
 * Configured for image uploads with validation.
 */

const multer = require('multer');
const path = require('path');
const { ALLOWED_IMAGE_TYPES, MAX_FILE_SIZE } = require('../config/constants');

// Storage configuration
const storage = multer.diskStorage({
    destination: (req, file, cb) => {
        cb(null, path.join(__dirname, '../../uploads'));
    },
    filename: (req, file, cb) => {
        // Generate unique filename: userId-timestamp-originalname
        const userId = req.user?.userId || 'anonymous';
        const timestamp = Date.now();
        const ext = path.extname(file.originalname);
        const name = path.basename(file.originalname, ext)
            .replace(/[^a-zA-Z0-9]/g, '_')
            .substring(0, 20);

        cb(null, `${userId}-${timestamp}-${name}${ext}`);
    }
});

// File filter - only allow images
const fileFilter = (req, file, cb) => {
    if (ALLOWED_IMAGE_TYPES.includes(file.mimetype)) {
        cb(null, true);
    } else {
        cb(new Error(`Invalid file type. Allowed: ${ALLOWED_IMAGE_TYPES.join(', ')}`), false);
    }
};

// Create multer instance
const upload = multer({
    storage,
    fileFilter,
    limits: {
        fileSize: MAX_FILE_SIZE
    }
});

// Single image upload
const uploadSingle = upload.single('image');

// Wrapper to handle multer errors
function handleUpload(req, res, next) {
    uploadSingle(req, res, (err) => {
        if (err instanceof multer.MulterError) {
            if (err.code === 'LIMIT_FILE_SIZE') {
                return res.status(400).json({
                    success: false,
                    message: `File too large. Max size: ${MAX_FILE_SIZE / (1024 * 1024)}MB`
                });
            }
            return res.status(400).json({
                success: false,
                message: err.message
            });
        } else if (err) {
            return res.status(400).json({
                success: false,
                message: err.message
            });
        }
        next();
    });
}

module.exports = {
    upload,
    uploadSingle,
    handleUpload
};
