import { useEffect, useMemo, useState } from 'react';
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { api, normalizeVideoUrl } from '../utils/api';
import { auth } from '../utils/auth';

const getVideoTitle = (video) => {
    const primaryTitle = video.landmark_name?.trim();
    if (primaryTitle) {
        return primaryTitle;
    }

    const locationTitle = video.location?.trim();
    if (locationTitle) {
        return locationTitle;
    }

    return 'Untitled Landmark';
};

const parseSelectedIds = (rawValue) => {
    if (!rawValue) {
        return [];
    }

    const ids = rawValue
        .split(',')
        .map((part) => Number.parseInt(part.trim(), 10))
        .filter((value) => Number.isInteger(value) && value > 0);

    return Array.from(new Set(ids)).sort((a, b) => a - b);
};

const normalizeSelectedIds = (ids) => {
    return Array.from(
        new Set(
            ids
                .map((value) => Number.parseInt(value, 10))
                .filter((item) => Number.isInteger(item) && item > 0)
        )
    ).sort((a, b) => a - b);
};

const History = () => {
    const navigate = useNavigate();
    const location = useLocation();
    const [searchParams, setSearchParams] = useSearchParams();

    const initialPage = Math.max(1, Number.parseInt(searchParams.get('page') || '1', 10) || 1);
    const initialSearch = searchParams.get('q') || '';
    const initialStatusRaw = searchParams.get('status') || 'all';
    const initialStatus = ['all', 'completed', 'processing', 'failed'].includes(initialStatusRaw)
        ? initialStatusRaw
        : 'all';
    const initialSelected = parseSelectedIds(searchParams.get('sel'));

    const [loading, setLoading] = useState(true);
    const [page, setPage] = useState(initialPage);
    const [totalPages, setTotalPages] = useState(1);
    const [videos, setVideos] = useState([]);
    const [stats, setStats] = useState({ completed: 0, unesco_sites: 0 });
    const [errorMessage, setErrorMessage] = useState('');
    const [searchTerm, setSearchTerm] = useState(initialSearch);
    const [statusFilter, setStatusFilter] = useState(initialStatus);
    const [selectedVideoIds, setSelectedVideoIds] = useState(initialSelected);
    const [isBulkDeleting, setIsBulkDeleting] = useState(false);

    useEffect(() => {
        if (!auth.isLoggedIn()) {
            navigate('/login', { replace: true });
            return;
        }

        loadStats();
    }, [navigate]);

    useEffect(() => {
        if (!auth.isLoggedIn()) {
            return;
        }

        loadVideos(page, searchTerm, statusFilter);
    }, [page, searchTerm, statusFilter]);

    useEffect(() => {
        const params = new URLSearchParams(location.search);
        const urlPage = Math.max(1, Number.parseInt(params.get('page') || '1', 10) || 1);
        const urlSearch = params.get('q') || '';
        const urlStatusRaw = params.get('status') || 'all';
        const urlStatus = ['all', 'completed', 'processing', 'failed'].includes(urlStatusRaw)
            ? urlStatusRaw
            : 'all';
        const urlSelected = parseSelectedIds(params.get('sel'));

        if (urlPage !== page) {
            setPage(urlPage);
        }

        if (urlSearch !== searchTerm) {
            setSearchTerm(urlSearch);
        }

        if (urlStatus !== statusFilter) {
            setStatusFilter(urlStatus);
        }

        const localSelected = normalizeSelectedIds(selectedVideoIds);
        const selectedChanged = localSelected.length !== urlSelected.length
            || localSelected.some((value, index) => value !== urlSelected[index]);

        if (selectedChanged) {
            setSelectedVideoIds(urlSelected);
        }
    }, [location.search]);

    useEffect(() => {
        const nextParams = new URLSearchParams();

        if (page > 1) {
            nextParams.set('page', String(page));
        }

        if (searchTerm.trim()) {
            nextParams.set('q', searchTerm.trim());
        }

        if (statusFilter !== 'all') {
            nextParams.set('status', statusFilter);
        }

        const normalizedSelected = normalizeSelectedIds(selectedVideoIds);
        if (normalizedSelected.length > 0) {
            nextParams.set('sel', normalizedSelected.join(','));
        }

        const normalizedCurrent = new URLSearchParams(location.search);
        const samePage = (normalizedCurrent.get('page') || '1') === (nextParams.get('page') || '1');
        const sameQuery = (normalizedCurrent.get('q') || '') === (nextParams.get('q') || '');
        const sameStatus = (normalizedCurrent.get('status') || 'all') === (nextParams.get('status') || 'all');
        const sameSelected = (normalizedCurrent.get('sel') || '') === (nextParams.get('sel') || '');

        if (!samePage || !sameQuery || !sameStatus || !sameSelected) {
            setSearchParams(nextParams, { replace: true });
        }
    }, [page, searchTerm, statusFilter, selectedVideoIds, location.search, setSearchParams]);

    const totalVideos = useMemo(() => videos.length, [videos]);
    const selectedCount = selectedVideoIds.length;
    const allVisibleSelected = videos.length > 0 && videos.every((video) => selectedVideoIds.includes(video.id));



    const loadStats = async () => {
        try {
            const response = await api.get('/videos/stats');
            setStats(response.data || { completed: 0, unesco_sites: 0 });
        } catch (requestError) {
            setErrorMessage(requestError.message || 'Failed to load stats.');
        }
    };

    const loadVideos = async (targetPage, searchValue = '', statusValue = 'all') => {
        setLoading(true);
        setErrorMessage('');

        try {
            const query = new URLSearchParams({
                page: String(targetPage),
                limit: '9',
                search: searchValue.trim(),
                status: statusValue
            });

            const response = await api.get(`/videos?${query.toString()}`);
            const payload = response.data || {};
            const list = Array.isArray(payload.videos)
                ? payload.videos
                : Array.isArray(payload)
                    ? payload
                    : [];

            setVideos(list);
            setTotalPages(payload.totalPages || 1);

            const maxPage = Math.max(1, payload.totalPages || 1);
            if (targetPage > maxPage) {
                setPage(maxPage);
            }
        } catch (requestError) {
            setVideos([]);
            setErrorMessage(requestError.message || 'Failed to load videos.');
        } finally {
            setLoading(false);
        }
    };

    const toggleVideoSelection = (videoId) => {
        setSelectedVideoIds((previousIds) => {
            if (previousIds.includes(videoId)) {
                return previousIds.filter((id) => id !== videoId);
            }

            return [...previousIds, videoId];
        });
    };

    const toggleSelectAllVisible = () => {
        if (allVisibleSelected) {
            const visibleIds = new Set(videos.map((video) => video.id));
            setSelectedVideoIds((previousIds) => previousIds.filter((id) => !visibleIds.has(id)));
            return;
        }

        const visibleIds = videos.map((video) => video.id);
        setSelectedVideoIds((previousIds) => Array.from(new Set([...previousIds, ...visibleIds])));
    };

    const handleDeleteSelected = async () => {
        if (selectedVideoIds.length === 0 || isBulkDeleting) {
            return;
        }

        const shouldDelete = window.confirm(`Delete ${selectedVideoIds.length} selected video(s)?`);
        if (!shouldDelete) {
            return;
        }

        setIsBulkDeleting(true);
        setErrorMessage('');

        try {
            const results = await Promise.allSettled(
                selectedVideoIds.map((videoId) => api.delete(`/videos/${videoId}`))
            );

            const failedCount = results.filter((result) => result.status === 'rejected').length;

            setSelectedVideoIds([]);
            await Promise.all([loadStats(), loadVideos(page)]);

            if (failedCount > 0) {
                setErrorMessage(`${failedCount} video(s) could not be deleted. Please retry.`);
            }
        } catch (requestError) {
            setErrorMessage(requestError.message || 'Bulk delete failed.');
        } finally {
            setIsBulkDeleting(false);
        }
    };

    return (
        <section className="history-page-shell">
            <div className="container">
                <header className="history-header-row">
                    <div>
                        <h1>My Videos</h1>
                        <p>All your generated documentaries in one place.</p>
                    </div>
                    <Link to="/dashboard" className="btn btn-primary">Create New</Link>
                </header>

                {errorMessage && <p className="auth-error dashboard-error-inline">{errorMessage}</p>}

                <div className="history-stats-grid">
                    <article className="history-stat-card">
                        <span>🎬</span>
                        <div>
                            <strong>{totalVideos}</strong>
                            <small>Loaded This Page</small>
                        </div>
                    </article>
                    <article className="history-stat-card">
                        <span>✅</span>
                        <div>
                            <strong>{stats.completed || 0}</strong>
                            <small>Total Completed</small>
                        </div>
                    </article>
                    <article className="history-stat-card">
                        <span>🏛️</span>
                        <div>
                            <strong>{stats.unesco_sites || 0}</strong>
                            <small>UNESCO Sites</small>
                        </div>
                    </article>
                </div>

                <div className="history-filters">
                    <input
                        type="text"
                        className="form-input history-search-input"
                        placeholder="Search by landmark or location"
                        value={searchTerm}
                        onChange={(event) => {
                            setSearchTerm(event.target.value);
                            setPage(1);
                        }}
                    />
                    <select
                        className="history-status-select"
                        value={statusFilter}
                        onChange={(event) => {
                            setStatusFilter(event.target.value);
                            setPage(1);
                        }}
                    >
                        <option value="all">All Status</option>
                        <option value="completed">Completed</option>
                        <option value="processing">Processing</option>
                        <option value="failed">Failed</option>
                    </select>
                </div>

                <div className="history-bulk-bar">
                    <label className="history-select-all">
                        <input
                            type="checkbox"
                            checked={allVisibleSelected}
                            onChange={toggleSelectAllVisible}
                        />
                        <span>Select all visible</span>
                    </label>

                    <button
                        type="button"
                        className="btn history-delete-btn"
                        disabled={selectedCount === 0 || isBulkDeleting}
                        onClick={handleDeleteSelected}
                    >
                        {isBulkDeleting ? 'Deleting...' : `Delete Selected (${selectedCount})`}
                    </button>
                </div>

                {loading ? (
                    <div className="history-state-card">
                        <p>Loading your videos...</p>
                    </div>
                ) : videos.length === 0 ? (
                    <div className="history-state-card">
                        {searchTerm.trim() || statusFilter !== 'all' ? (
                            <>
                                <h3>No matching videos</h3>
                                <p>Try a different search term or status filter.</p>
                            </>
                        ) : (
                            <>
                                <h3>No videos yet</h3>
                                <p>Create your first documentary to see it here.</p>
                                <Link to="/dashboard" className="btn btn-primary">Create Documentary</Link>
                            </>
                        )}
                    </div>
                ) : (
                    <>
                        <div className="history-grid">
                            {videos.map((video) => (
                                <article key={video.id} className="history-video-card">
                                    <label className="history-card-checkbox" onClick={(event) => event.stopPropagation()}>
                                        <input
                                            type="checkbox"
                                            checked={selectedVideoIds.includes(video.id)}
                                            onChange={() => toggleVideoSelection(video.id)}
                                        />
                                    </label>

                                    <Link
                                        to={`/history/${video.id}?from=${encodeURIComponent(`/history${location.search || ''}`)}`}
                                        className="history-card-anchor"
                                        aria-label={`View details for ${getVideoTitle(video)}`}
                                    >
                                        <div className="history-video-thumb">
                                            {video.thumbnail_url ? (
                                                <img src={normalizeVideoUrl(video.thumbnail_url)} alt={getVideoTitle(video)} />
                                            ) : video.video_url ? (
                                                <video
                                                    className="history-thumb-video"
                                                    src={normalizeVideoUrl(video.video_url)}
                                                    muted
                                                    preload="metadata"
                                                    playsInline
                                                />
                                            ) : (
                                                <span>🎬</span>
                                            )}
                                            <em className={`history-status-chip status-${video.status}`}>{video.status}</em>
                                        </div>
                                        <div className="history-video-info">
                                            <h4>{getVideoTitle(video)}</h4>
                                        </div>
                                        <span className="history-card-link">View Details</span>
                                    </Link>
                                </article>
                            ))}
                        </div>

                        <div className="history-pagination">
                            <button type="button" className="btn btn-outline" disabled={page <= 1} onClick={() => setPage((previous) => previous - 1)}>
                                Previous
                            </button>
                            <span>Page {page} of {totalPages}</span>
                            <button type="button" className="btn btn-outline" disabled={page >= totalPages} onClick={() => setPage((previous) => previous + 1)}>
                                Next
                            </button>
                        </div>
                    </>
                )}
            </div>
        </section>
    );
};

export default History;
