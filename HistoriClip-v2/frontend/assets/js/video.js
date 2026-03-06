/**
 * HistoriClip - Video Generation JavaScript
 * 
 * Handles file upload and video generation
 */

let selectedFile = null;

document.addEventListener('DOMContentLoaded', () => {
    // Check auth
    if (!requireAuth()) return;

    // Elements
    const dropZone = document.getElementById('dropZone');
    const imageInput = document.getElementById('imageInput');
    const previewSection = document.getElementById('previewSection');
    const previewImage = document.getElementById('previewImage');
    const removeImageBtn = document.getElementById('removeImage');
    const generateBtn = document.getElementById('generateBtn');
    const uploadForm = document.getElementById('uploadForm');

    // Drop zone click
    dropZone.addEventListener('click', () => imageInput.click());

    // File input change
    imageInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileSelect(e.target.files[0]);
        }
    });

    // Drag and drop
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('drag-over');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('drag-over');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('drag-over');

        if (e.dataTransfer.files.length > 0) {
            handleFileSelect(e.dataTransfer.files[0]);
        }
    });

    // Remove image
    removeImageBtn.addEventListener('click', () => {
        resetUpload();
    });

    // Form submit
    uploadForm.addEventListener('submit', handleGenerate);

    // Create another button
    const createNewBtn = document.getElementById('createNewBtn');
    if (createNewBtn) {
        createNewBtn.addEventListener('click', () => {
            resetAll();
        });
    }

    // Retry button
    const retryBtn = document.getElementById('retryBtn');
    if (retryBtn) {
        retryBtn.addEventListener('click', () => {
            resetAll();
        });
    }
});

function handleFileSelect(file) {
    // Validate file type
    const validTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp'];
    if (!validTypes.includes(file.type)) {
        alert('Please select a valid image file (JPG, PNG, or WebP)');
        return;
    }

    // Validate file size (10MB)
    if (file.size > 10 * 1024 * 1024) {
        alert('File size must be less than 10MB');
        return;
    }

    selectedFile = file;

    // Show preview
    const reader = new FileReader();
    reader.onload = (e) => {
        document.getElementById('previewImage').src = e.target.result;
        document.getElementById('previewSection').style.display = 'block';
        document.getElementById('dropZone').style.display = 'none';
        document.getElementById('generateBtn').disabled = false;
    };
    reader.readAsDataURL(file);
}

function resetUpload() {
    selectedFile = null;
    document.getElementById('imageInput').value = '';
    document.getElementById('previewSection').style.display = 'none';
    document.getElementById('dropZone').style.display = 'block';
    document.getElementById('generateBtn').disabled = true;
}

function resetAll() {
    resetUpload();
    document.getElementById('uploadForm').style.display = 'block';
    document.getElementById('processingSection').style.display = 'none';
    document.getElementById('resultSection').style.display = 'none';
    document.getElementById('errorSection').style.display = 'none';

    // Reset processing steps
    document.querySelectorAll('.step-item').forEach(el => {
        el.classList.remove('active', 'completed');
    });
}

async function handleGenerate(e) {
    e.preventDefault();

    if (!selectedFile) {
        alert('Please select an image first');
        return;
    }

    const generateBtn = document.getElementById('generateBtn');
    const btnText = generateBtn.querySelector('.btn-text');
    const btnLoader = generateBtn.querySelector('.btn-loader');

    // Show processing
    document.getElementById('uploadForm').style.display = 'none';
    document.getElementById('processingSection').style.display = 'block';

    // Simulate step progress
    animateSteps();

    try {
        // Create form data
        const formData = new FormData();
        formData.append('image', selectedFile);

        // Add duration/speed
        const speed = document.querySelector('input[name="duration"]:checked').value;
        formData.append('duration', speed); // 'normal' or 'fast'

        // Send to API
        const response = await API.upload('/analyze', formData);

        // Start polling instead of assuming immediate completion
        if (response.data && response.data.id) {
            pollForVideoCompletion(response.data.id);
        } else {
            showErrorState('Invalid response from server');
        }

    } catch (error) {
        showErrorState(error.message || 'Video generation initialization failed');
    }
}

async function pollForVideoCompletion(videoId) {
    const maxRetries = 240; // 240 * 5s = 20 minutes (plenty of time for heavy AI models)
    let retries = 0;

    const checkStatus = async () => {
        try {
            const response = await API.get(`/videos/${videoId}`);
            const data = response.data;

            if (data.status === 'completed') {
                showResult(data);
            } else if (data.status === 'failed') {
                showErrorState(data.error_message || 'Video generation failed during processing');
            } else {
                // Still processing
                retries++;
                if (retries > maxRetries) {
                    showErrorState('Video generation timed out. Please check your History/Dashboard later.');
                    return;
                }
                setTimeout(checkStatus, 5000); // Poll every 5 seconds
            }
        } catch (error) {
            console.error('Polling error:', error);
            // It might be a momentary network error, we can retry a network drop if we want, but letting it fail is safer.
            showErrorState(error.message || 'Error checking status during generation');
        }
    };

    // Start first poll after 5 seconds
    setTimeout(checkStatus, 5000);
}

function animateSteps() {
    const steps = ['step1', 'step2', 'step3', 'step4', 'step5'];
    const statusMessages = [
        'Detecting landmark...',
        'Researching historical facts...',
        'Generating AI images...',
        'Creating voice narration...',
        'Assembling final video...'
    ];

    let currentStep = 0;

    const interval = setInterval(() => {
        if (currentStep > 0) {
            document.getElementById(steps[currentStep - 1]).classList.remove('active');
            document.getElementById(steps[currentStep - 1]).classList.add('completed');
        }

        if (currentStep < steps.length) {
            document.getElementById(steps[currentStep]).classList.add('active');
            document.getElementById('processingStatus').textContent = statusMessages[currentStep];
            currentStep++;
        } else {
            clearInterval(interval);
        }
    }, 10000); // 10 seconds per step for demo

    // Store interval to clear on success/error
    window.stepInterval = interval;
}

function showResult(data) {
    // Clear step animation
    if (window.stepInterval) {
        clearInterval(window.stepInterval);
    }

    // Hide processing
    document.getElementById('processingSection').style.display = 'none';

    // Show result
    document.getElementById('resultSection').style.display = 'block';

    // Populate data
    document.getElementById('landmarkName').textContent = data.landmark_name;
    // Handle location - can be object or string
    let locationText = 'Location detected';
    if (data.location) {
        if (typeof data.location === 'object') {
            locationText = data.location.name || data.location.display_name || JSON.stringify(data.location);
        } else {
            locationText = data.location;
        }
    }
    document.getElementById('locationInfo').textContent = `📍 ${locationText}`;
    document.getElementById('scriptText').textContent = data.script;

    // UNESCO badge
    if (data.is_unesco) {
        document.getElementById('unescoBadge').style.display = 'inline-block';
    }

    // Video
    if (data.video_url) {
        const video = document.getElementById('resultVideo');
        video.querySelector('source').src = data.video_url;
        video.load();
    }

    // Download button
    document.getElementById('downloadBtn').onclick = async () => {
        if (data.video_url) {
            let downloadUrl = data.video_url;
            if (downloadUrl.startsWith('http://localhost:5001')) {
                downloadUrl = downloadUrl.replace('http://localhost:5001', 'http://localhost:5000');
            }

            // Pass the URL to the dedicated backend download route
            const backendDownloadUrl = API_URL.replace(/\/api$/, '') + '/download?url=' + encodeURIComponent(downloadUrl);
            const filename = 'HistoriClip_' + (data.landmark_name || 'Video') + '.mp4';

            try {
                const response = await fetch(backendDownloadUrl);
                if (!response.ok) throw new Error('Download failed');
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const link = document.createElement('a');
                link.href = url;
                link.download = filename;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                window.URL.revokeObjectURL(url);
            } catch (error) {
                console.error('Download error:', error);
                alert('Failed to download video. Please try again.');
            }
        }
    };
}

function showErrorState(message) {
    // Clear step animation
    if (window.stepInterval) {
        clearInterval(window.stepInterval);
    }

    document.getElementById('processingSection').style.display = 'none';
    document.getElementById('errorSection').style.display = 'block';
    document.getElementById('errorMessage').textContent = message;
}
