/**
 * HistoriClip - History Page JavaScript
 * 
 * Handles video history display and management
 */

let currentPage = 1;
let totalPages = 1;
let currentVideo = null;

document.addEventListener('DOMContentLoaded', () => {
    // Check auth
    if (!requireAuth()) return;

    // Load data
    loadStats();
    loadVideos();

    // Pagination
    document.getElementById('prevBtn').addEventListener('click', () => {
        if (currentPage > 1) {
            currentPage--;
            loadVideos();
        }
    });

    document.getElementById('nextBtn').addEventListener('click', () => {
        if (currentPage < totalPages) {
            currentPage++;
            loadVideos();
        }
    });

    // Modal handlers
    document.getElementById('modalOverlay').addEventListener('click', closeModal);
    document.getElementById('modalClose').addEventListener('click', closeModal);
    document.getElementById('modalDownload').addEventListener('click', downloadVideo);
    document.getElementById('modalDelete').addEventListener('click', deleteVideo);
});

async function loadStats() {
    try {
        const response = await API.get('/videos/stats');
        const stats = response.data;

        document.getElementById('totalVideos').textContent = stats.completed || 0;
        document.getElementById('completedVideos').textContent = stats.completed || 0;
        document.getElementById('unescoCount').textContent = stats.unesco_sites || 0;
    } catch (error) {
        console.error('Failed to load stats:', error);
    }
}

async function loadVideos() {
    const loadingState = document.getElementById('loadingState');
    const emptyState = document.getElementById('emptyState');
    const videosGrid = document.getElementById('videosGrid');
    const pagination = document.getElementById('pagination');

    loadingState.style.display = 'block';
    emptyState.style.display = 'none';
    videosGrid.style.display = 'none';
    pagination.style.display = 'none';

    try {
        // console.log('Fetching videos...');
        const response = await API.get('/videos?page=' + currentPage + '&limit=9');
        console.log('Videos API Response:', response); // Debug log

        // Handle different response structures
        let videos = [];
        let total = 0;
        let pages = 0;

        // Debug logging to understand exact structure
        // console.log('Parsing response:', response);

        if (response.data && Array.isArray(response.data.videos)) {
            // Structure: { data: { videos: [], total: 0, ... } }
            videos = response.data.videos;
            total = response.data.total;
            pages = response.data.totalPages;
        } else if (response.data && Array.isArray(response.data)) {
            // Structure: { data: [] }
            videos = response.data;
            total = videos.length;
            pages = 1;
        } else if (response.videos && Array.isArray(response.videos)) {
            // Structure: { videos: [], total: 0, ... } (direct return)
            videos = response.videos;
            total = response.total;
            pages = response.totalPages;
        } else if (Array.isArray(response)) {
            // Structure: []
            videos = response;
            total = videos.length;
            pages = 1;
        }

        // Final fallback if videos is still undefined/null
        videos = videos || [];

        totalPages = pages || 1;

        loadingState.style.display = 'none';

        if (!videos || videos.length === 0) {
            emptyState.style.display = 'block';
            pagination.style.display = 'none';
        } else {
            videosGrid.style.display = 'grid';
            renderVideos(videos);

            if (totalPages > 1) {
                pagination.style.display = 'flex';
                updatePagination();
            }
        }
    } catch (error) {
        loadingState.style.display = 'none';
        emptyState.style.display = 'block';
        console.error('Failed to load videos:', error);

        // Optional: Show error message in empty state
        const emptyText = emptyState.querySelector('p');
        if (emptyText) emptyText.textContent = `Error: ${error.message}`;
    }
}

function renderVideos(videos) {
    const grid = document.getElementById('videosGrid');
    grid.innerHTML = '';

    videos.forEach(video => {
        const card = document.createElement('div');
        card.className = 'video-card';
        card.onclick = () => openModal(video);

        card.innerHTML = `
            <div class="video-thumbnail">
                ${video.thumbnail_url
                ? `<img src="${video.thumbnail_url}" alt="${video.landmark_name}">`
                : `<span class="play-icon">🎬</span>`
            }
                <span class="video-status ${video.status}">${video.status}</span>
            </div>
            <div class="video-card-content">
                <h3>${video.landmark_name}</h3>
                <p>${formatDate(video.created_at)}</p>
            </div>
        `;

        grid.appendChild(card);
    });
}

function updatePagination() {
    document.getElementById('pageInfo').textContent = `Page ${currentPage} of ${totalPages}`;
    document.getElementById('prevBtn').disabled = currentPage === 1;
    document.getElementById('nextBtn').disabled = currentPage === totalPages;
}

function openModal(video) {
    currentVideo = video;

    const modal = document.getElementById('videoModal');
    modal.style.display = 'flex';

    // Populate modal
    document.getElementById('modalTitle').textContent = video.landmark_name;
    document.getElementById('modalLocation').textContent = `📍 ${video.location || 'Unknown'}`;
    document.getElementById('modalDate').textContent = `📅 ${formatDate(video.created_at)}`;
    document.getElementById('modalScript').textContent = video.script || 'No script available';

    // UNESCO badge
    const unescoBadge = document.getElementById('modalUnesco');
    unescoBadge.style.display = video.is_unesco ? 'inline-block' : 'none';

    // Video
    const modalVideo = document.getElementById('modalVideo');
    if (video.video_url) {
        modalVideo.querySelector('source').src = video.video_url;
        modalVideo.load();
        modalVideo.style.display = 'block';
    } else {
        modalVideo.style.display = 'none';
    }
}

function closeModal() {
    document.getElementById('videoModal').style.display = 'none';
    currentVideo = null;

    // Pause video
    const modalVideo = document.getElementById('modalVideo');
    modalVideo.pause();
}

async function downloadVideo() {
    if (!currentVideo || !currentVideo.video_url) return;

    const filename = 'HistoriClip_' + (currentVideo.landmark_name || 'Video').replace(/[^a-zA-Z0-9_ ]/g, '') + '.mp4';

    // Normalize URL: ensure it goes through backend (port 5000), not AI service (5001)
    let videoUrl = currentVideo.video_url;
    if (videoUrl.startsWith('http://localhost:5001')) {
        videoUrl = videoUrl.replace('http://localhost:5001', 'http://localhost:5000');
    } else if (videoUrl.startsWith('/uploads')) {
        videoUrl = API_URL.replace(/\/api$/, '') + videoUrl;
    }

    try {
        // Fetch video as blob — this forces a real download instead of browser navigation
        const response = await fetch(videoUrl);
        if (!response.ok) throw new Error('Download failed: ' + response.status);

        const blob = await response.blob();
        const blobUrl = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = blobUrl;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(blobUrl);
    } catch (error) {
        console.error('Download error:', error);
        alert('Download failed. Please try again.');
    }
}

async function deleteVideo() {
    if (!currentVideo) return;

    if (!confirm('Are you sure you want to delete this video?')) {
        return;
    }

    try {
        await API.delete(`/videos/${currentVideo.id}`);

        closeModal();
        loadStats();
        loadVideos();

    } catch (error) {
        alert('Failed to delete video: ' + error.message);
    }
}
