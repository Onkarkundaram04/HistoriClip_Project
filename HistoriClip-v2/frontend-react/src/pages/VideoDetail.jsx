import { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Download, Trash2, Brain, Eye, Search, Layers, ChevronDown, ChevronUp, ZoomIn } from 'lucide-react';
import { api, normalizeVideoUrl } from '../utils/api';
import { auth } from '../utils/auth';

const formatDate = (dateString) => {
    if (!dateString) {
        return 'Unknown date';
    }

    return new Date(dateString).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
};

const TIER_INFO = {
    tier1_landmark: {
        label: 'Tier 1 — Cloud Vision',
        description: 'Identified via Google Cloud Vision landmark database',
        color: '#10b981',
        icon: '☁️'
    },
    tier2_gps: {
        label: 'Tier 2 — EXIF GPS',
        description: 'Located via embedded GPS metadata + reverse geocoding',
        color: '#3b82f6',
        icon: '📍'
    },
    tier3_faiss_geocode: {
        label: 'Tier 3 — Visual Match + Geocode',
        description: 'DINOv2+FAISS visual retrieval → reverse geocoding identified the landmark',
        color: '#8b5cf6',
        icon: '🔍'
    },
    tier3_faiss_vlm: {
        label: 'Tier 3.5 — Visual Match + VLM',
        description: 'DINOv2+FAISS visual retrieval → Gemini VLM identified the landmark using geographic context',
        color: '#f59e0b',
        icon: '🧠'
    },
    tier3_faiss_unresolved: {
        label: 'Tier 3 — Visual Match (Unresolved)',
        description: 'DINOv2+FAISS located the area but couldn\'t identify a specific landmark',
        color: '#ef4444',
        icon: '⚠️'
    },
    tier3_dinov2_gem: {
        label: 'Tier 3 — DINOv2 + FAISS',
        description: 'Identified via visual place recognition with DINOv2 features and FAISS retrieval',
        color: '#8b5cf6',
        icon: '🔍'
    }
};

const VideoDetail = () => {
    const { id } = useParams();
    const location = useLocation();
    const navigate = useNavigate();
    const [loading, setLoading] = useState(true);
    const [video, setVideo] = useState(null);
    const [errorMessage, setErrorMessage] = useState('');
    const [deleting, setDeleting] = useState(false);
    const [xaiExpanded, setXaiExpanded] = useState(true);
    const [zoomedImage, setZoomedImage] = useState(null);

    const fromParam = new URLSearchParams(location.search).get('from');
    const backToHistory = fromParam && fromParam.startsWith('/history') ? fromParam : '/history';

    useEffect(() => {
        if (!auth.isLoggedIn()) {
            navigate('/login', { replace: true });
            return;
        }

        const loadVideo = async () => {
            setLoading(true);
            setErrorMessage('');

            try {
                const response = await api.get(`/videos/${id}`);
                setVideo(response.data || null);
            } catch (requestError) {
                setErrorMessage(requestError.message || 'Failed to load video details.');
            } finally {
                setLoading(false);
            }
        };

        loadVideo();
    }, [id, navigate]);

    const handleDownload = async () => {
        if (!video?.video_url) {
            return;
        }

        try {
            const response = await fetch(normalizeVideoUrl(video.video_url));
            if (!response.ok) {
                throw new Error('Download failed');
            }

            const blob = await response.blob();
            const blobUrl = URL.createObjectURL(blob);
            const anchor = document.createElement('a');
            anchor.href = blobUrl;
            anchor.download = `HistoriClip_${(video.landmark_name || 'Video').replace(/[^a-zA-Z0-9_ ]/g, '')}.mp4`;
            document.body.appendChild(anchor);
            anchor.click();
            document.body.removeChild(anchor);
            URL.revokeObjectURL(blobUrl);
        } catch (downloadError) {
            setErrorMessage(downloadError.message || 'Download failed.');
        }
    };

    const handleDelete = async () => {
        if (!video?.id || deleting) {
            return;
        }

        const shouldDelete = window.confirm('Are you sure you want to delete this video?');
        if (!shouldDelete) {
            return;
        }

        setDeleting(true);
        try {
            await api.delete(`/videos/${video.id}`);
            navigate(backToHistory, { replace: true });
        } catch (requestError) {
            setErrorMessage(requestError.message || 'Failed to delete video.');
        } finally {
            setDeleting(false);
        }
    };

    const parseTopMatches = () => {
        if (!video?.xai_top_matches) return [];
        try {
            const data = typeof video.xai_top_matches === 'string'
                ? JSON.parse(video.xai_top_matches)
                : video.xai_top_matches;
            return Array.isArray(data) ? data : [];
        } catch {
            return [];
        }
    };

    const hasXaiData = video?.xai_matches_url || video?.xai_attention_url || video?.xai_top_matches || video?.xai_tier_used;

    const tierKey = video?.xai_tier_used || video?.method || '';
    const tierInfo = TIER_INFO[tierKey] || null;

    const topMatches = parseTopMatches();

    if (loading) {
        return (
            <section className="video-detail-shell">
                <div className="container">
                    <div className="history-state-card">
                        <p>Loading video details...</p>
                    </div>
                </div>
            </section>
        );
    }

    if (!video) {
        return (
            <section className="video-detail-shell">
                <div className="container">
                    <div className="history-state-card">
                        <h3>Video not found</h3>
                        <p>{errorMessage || 'The requested video does not exist or is unavailable.'}</p>
                        <Link to={backToHistory} className="btn btn-primary">Back to History</Link>
                    </div>
                </div>
            </section>
        );
    }

    return (
        <section className="video-detail-shell">
            <div className="container">
                <div className="video-detail-header">
                    <Link to={backToHistory} className="btn btn-outline">
                        <ArrowLeft size={16} /> Back to History
                    </Link>
                    <div className="video-detail-actions">
                        <button type="button" className="btn btn-primary" onClick={handleDownload}>
                            <Download size={16} /> Download
                        </button>
                        <button type="button" className="btn history-delete-btn" onClick={handleDelete} disabled={deleting}>
                            <Trash2 size={16} /> {deleting ? 'Deleting...' : 'Delete'}
                        </button>
                    </div>
                </div>

                {errorMessage && <p className="auth-error dashboard-error-inline">{errorMessage}</p>}

                <article className="video-detail-card">
                    <div className="video-detail-layout">
                        <div className="video-detail-player-wrap">
                            <video controls className="video-detail-player" src={normalizeVideoUrl(video.video_url)} />
                        </div>

                        <div className="video-detail-meta">
                            <h1>{video.landmark_name || 'Landmark'}</h1>
                            <p>📅 {formatDate(video.created_at)}</p>
                            <p>📍 {video.location || 'Unknown location'}</p>
                            {!!video.is_unesco && <span className="unesco-chip">UNESCO World Heritage Site</span>}

                            <div className="script-box">
                                <strong>Script</strong>
                                <p>{video.script || 'No script available.'}</p>
                            </div>
                        </div>
                    </div>
                </article>

                {/* ═══════════ XAI SECTION ═══════════ */}
                {hasXaiData && (
                    <section className="xai-section" id="xai-analysis">
                        <button
                            type="button"
                            className="xai-section-header"
                            onClick={() => setXaiExpanded(!xaiExpanded)}
                        >
                            <div className="xai-header-left">
                                <Brain size={22} />
                                <div>
                                    <h2>Explainable AI Analysis</h2>
                                    <p>Visual evidence of how HistoriClip identified this landmark</p>
                                </div>
                            </div>
                            {xaiExpanded ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
                        </button>

                        {xaiExpanded && (
                            <div className="xai-content">

                                {/* Tier Badge */}
                                {tierInfo && (
                                    <div className="xai-tier-card">
                                        <div className="xai-tier-badge" style={{ '--tier-color': tierInfo.color }}>
                                            <span className="xai-tier-icon">{tierInfo.icon}</span>
                                            <div>
                                                <strong>{tierInfo.label}</strong>
                                                <p>{tierInfo.description}</p>
                                            </div>
                                        </div>
                                    </div>
                                )}

                                {/* LightGlue Keypoint Verification */}
                                {video.xai_matches_url && (
                                    <div className="xai-card">
                                        <div className="xai-card-header">
                                            <Layers size={18} />
                                            <div>
                                                <h3>LightGlue Keypoint Verification</h3>
                                                <p>Geometric verification between your photo and the closest database match via DISK + LightGlue sparse keypoint matching</p>
                                            </div>
                                        </div>
                                        <div
                                            className="xai-image-wrap"
                                            onClick={() => setZoomedImage(normalizeVideoUrl(video.xai_matches_url))}
                                        >
                                            <img
                                                src={normalizeVideoUrl(video.xai_matches_url)}
                                                alt="LightGlue keypoint correspondence visualization"
                                                className="xai-image"
                                            />
                                            <div className="xai-image-overlay">
                                                <ZoomIn size={24} />
                                                <span>Click to enlarge</span>
                                            </div>
                                        </div>
                                    </div>
                                )}

                                {/* DINOv2 Attention Map */}
                                {video.xai_attention_url && (
                                    <div className="xai-card">
                                        <div className="xai-card-header">
                                            <Eye size={18} />
                                            <div>
                                                <h3>DINOv2 Attention Map</h3>
                                                <p>Self-attention heatmap showing which regions DINOv2 focuses on for feature extraction</p>
                                            </div>
                                        </div>
                                        <div
                                            className="xai-image-wrap"
                                            onClick={() => setZoomedImage(normalizeVideoUrl(video.xai_attention_url))}
                                        >
                                            <img
                                                src={normalizeVideoUrl(video.xai_attention_url)}
                                                alt="DINOv2 attention heatmap visualization"
                                                className="xai-image"
                                            />
                                            <div className="xai-image-overlay">
                                                <ZoomIn size={24} />
                                                <span>Click to enlarge</span>
                                            </div>
                                        </div>
                                    </div>
                                )}

                                {/* FAISS Top-K Retrieval Results */}
                                {topMatches.length > 0 && (
                                    <div className="xai-card">
                                        <div className="xai-card-header">
                                            <Search size={18} />
                                            <div>
                                                <h3>FAISS Retrieval Results</h3>
                                                <p>Top-{topMatches.length} nearest neighbors from the geo-tagged reference database ranked by cosine similarity</p>
                                            </div>
                                        </div>
                                        <div className="xai-matches-grid">
                                            {topMatches.map((match, index) => (
                                                <div key={index} className="xai-match-card">
                                                    {match.image_url && (
                                                        <div
                                                            className="xai-match-image-wrap"
                                                            onClick={() => setZoomedImage(normalizeVideoUrl(match.image_url))}
                                                        >
                                                            <img
                                                                src={normalizeVideoUrl(match.image_url)}
                                                                alt={`Match #${match.rank}`}
                                                                className="xai-match-image"
                                                            />
                                                        </div>
                                                    )}
                                                    <div className="xai-match-info">
                                                        <div className="xai-match-rank">
                                                            <span className="xai-rank-badge">#{match.rank}</span>
                                                            <span className="xai-match-name" title={match.name || 'Unknown'}>
                                                                {match.name || 'Unknown location'}
                                                            </span>
                                                        </div>
                                                        <div className="xai-similarity-bar-wrap">
                                                            <div className="xai-similarity-bar">
                                                                <div
                                                                    className="xai-similarity-fill"
                                                                    style={{ width: `${Math.min(match.similarity * 100, 100)}%` }}
                                                                />
                                                            </div>
                                                            <span className="xai-similarity-value">
                                                                {(match.similarity * 100).toFixed(1)}%
                                                            </span>
                                                        </div>
                                                        {match.inliers > 0 && (
                                                            <div className="xai-match-verification">
                                                                <span className={`xai-verified-badge ${match.verified ? 'xai-verified-yes' : 'xai-verified-weak'}`}>
                                                                    {match.verified ? '✓ Verified' : '~ Weak'}
                                                                </span>
                                                                <span className="xai-inlier-count">
                                                                    {match.inliers} keypoint matches
                                                                </span>
                                                            </div>
                                                        )}
                                                        {match.lat && match.lon && (
                                                            <p className="xai-match-coords">
                                                                ({match.lat.toFixed(4)}, {match.lon.toFixed(4)})
                                                            </p>
                                                        )}
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
                    </section>
                )}

                {/* Zoom Modal */}
                {zoomedImage && (
                    <div className="xai-zoom-modal" onClick={() => setZoomedImage(null)}>
                        <div className="xai-zoom-content" onClick={(e) => e.stopPropagation()}>
                            <button
                                type="button"
                                className="xai-zoom-close"
                                onClick={() => setZoomedImage(null)}
                            >
                                ✕
                            </button>
                            <img src={zoomedImage} alt="Zoomed XAI visualization" />
                        </div>
                    </div>
                )}
            </div>
        </section>
    );
};

export default VideoDetail;
