import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Camera, LoaderCircle, Sparkles, Download, RotateCcw } from 'lucide-react';
import { api, normalizeVideoUrl } from '../utils/api';
import { auth } from '../utils/auth';

const STEP_ITEMS = [
    { icon: '👁️', label: 'Detecting Landmark', key: 'vision' },
    { icon: '📚', label: 'Researching Facts', key: 'script' },
    { icon: '🎨', label: 'Generating Images', key: 'images' },
    { icon: '🎙️', label: 'Creating Narration', key: 'audio' },
    { icon: '🎬', label: 'Assembling Video', key: 'video' },
    { icon: '🧠', label: 'Processing XAI', key: 'xai' }
];

const STEP_MESSAGES = {
    vision: 'Analyzing image landmarks...',
    script: 'Researching historical facts...',
    images: 'Generating AI images...',
    audio: 'Creating voice narration...',
    video: 'Assembling final video...',
    xai: 'Generating explainability data...',
    complete: 'Finishing up...'
};

const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024;
const VALID_FILE_TYPES = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp'];

const Dashboard = () => {
    const navigate = useNavigate();
    const [selectedFile, setSelectedFile] = useState(null);
    const [previewUrl, setPreviewUrl] = useState('');
    const [phase, setPhase] = useState('upload');
    const [errorMessage, setErrorMessage] = useState('');
    const [activeStep, setActiveStep] = useState(0);
    const [processingStatus, setProcessingStatus] = useState('Analyzing image...');
    const [videoData, setVideoData] = useState(null);
    const [dragOver, setDragOver] = useState(false);
    const fileInputRef = useRef(null);

    useEffect(() => {
        if (!auth.isLoggedIn()) {
            navigate('/login', { replace: true });
        }
    }, [navigate]);

    const userDisplayName = useMemo(() => {
        const user = auth.getUser();
        return user?.name || user?.email || 'Creator';
    }, []);

    const validateFile = (file) => {
        if (!VALID_FILE_TYPES.includes(file.type)) {
            return 'Please select a valid image file (JPG, PNG, or WebP).';
        }

        if (file.size > MAX_FILE_SIZE_BYTES) {
            return 'File size must be under 10MB.';
        }

        return '';
    };

    const handleFilePicked = (file) => {
        const validationError = validateFile(file);
        if (validationError) {
            setErrorMessage(validationError);
            return;
        }

        setErrorMessage('');
        setSelectedFile(file);
        setPreviewUrl(URL.createObjectURL(file));
    };

    const resetAll = () => {
        setSelectedFile(null);
        setPreviewUrl('');
        setPhase('upload');
        setErrorMessage('');
        setActiveStep(0);
        setProcessingStatus('Analyzing image...');
        setVideoData(null);

        if (fileInputRef.current) {
            fileInputRef.current.value = '';
        }
    };

    const pollForCompletion = async (videoId, retryCount = 0) => {
        try {
            const response = await api.get(`/videos/${videoId}`);
            const latestVideo = response.data;

            // Update step progress from backend
            const step = latestVideo.processing_step;
            if (step && step !== 'queued') {
                const stepIndex = STEP_ITEMS.findIndex(s => s.key === step);
                if (stepIndex >= 0) {
                    setActiveStep(stepIndex);
                    setProcessingStatus(STEP_MESSAGES[step] || `Processing: ${step}`);
                } else if (step === 'complete') {
                    setActiveStep(STEP_ITEMS.length);
                    setProcessingStatus('Finishing up...');
                }
            }

            if (latestVideo.status === 'completed') {
                setVideoData(latestVideo);
                setPhase('result');
                return;
            }

            if (latestVideo.status === 'failed') {
                throw new Error(latestVideo.error_message || 'Video generation failed.');
            }

            if (retryCount >= 240) {
                throw new Error('Video generation timed out. Please check your history page later.');
            }

            window.setTimeout(() => {
                pollForCompletion(videoId, retryCount + 1);
            }, 3000);
        } catch (requestError) {
            setErrorMessage(requestError.message || 'Error while checking video status.');
            setPhase('error');
        }
    };

    const handleGenerate = async (event) => {
        event.preventDefault();

        if (!selectedFile) {
            setErrorMessage('Please select an image first.');
            return;
        }

        setErrorMessage('');
        setPhase('processing');

        try {
            const formData = new FormData();
            formData.append('image', selectedFile);
            formData.append('duration', 'normal');

            const response = await api.upload('/analyze', formData);
            const videoId = response?.data?.id;

            if (!videoId) {
                throw new Error('Video generation request failed.');
            }

            pollForCompletion(videoId);
        } catch (requestError) {
            setErrorMessage(requestError.message || 'Unable to start video generation.');
            setPhase('error');
        }
    };

    const handleDownload = async () => {
        if (!videoData?.video_url) {
            return;
        }

        try {
            const response = await fetch(normalizeVideoUrl(videoData.video_url));
            if (!response.ok) {
                throw new Error('Download failed');
            }

            const blob = await response.blob();
            const objectUrl = window.URL.createObjectURL(blob);
            const anchor = document.createElement('a');
            anchor.href = objectUrl;
            anchor.download = `HistoriClip_${(videoData.landmark_name || 'Video').replace(/[^a-zA-Z0-9_ ]/g, '')}.mp4`;
            document.body.appendChild(anchor);
            anchor.click();
            document.body.removeChild(anchor);
            window.URL.revokeObjectURL(objectUrl);
        } catch (downloadError) {
            setErrorMessage(downloadError.message || 'Unable to download video.');
            setPhase('error');
        }
    };

    const renderUploadArea = () => (
        <form onSubmit={handleGenerate} className="dashboard-card">
            <div
                className={`drop-zone ${dragOver ? 'drop-zone-active' : ''}`}
                onClick={() => fileInputRef.current?.click()}
                onDragOver={(event) => {
                    event.preventDefault();
                    setDragOver(true);
                }}
                onDragLeave={() => setDragOver(false)}
                onDrop={(event) => {
                    event.preventDefault();
                    setDragOver(false);
                    if (event.dataTransfer.files?.[0]) {
                        handleFilePicked(event.dataTransfer.files[0]);
                    }
                }}
            >
                <input
                    ref={fileInputRef}
                    type="file"
                    hidden
                    accept="image/jpeg,image/jpg,image/png,image/webp"
                    onChange={(event) => {
                        if (event.target.files?.[0]) {
                            handleFilePicked(event.target.files[0]);
                        }
                    }}
                />

                {previewUrl ? (
                    <div className="preview-wrap">
                        <img src={previewUrl} alt="Selected preview" className="preview-image" />
                        <button type="button" className="btn btn-ghost" onClick={(event) => {
                            event.stopPropagation();
                            resetAll();
                        }}>
                            Remove Image
                        </button>
                    </div>
                ) : (
                    <div className="drop-zone-content">
                        <Camera size={38} />
                        <h3>Drop your image here</h3>
                        <p>or click to browse</p>
                        <small>Supports JPG, PNG, WebP (Max 10MB)</small>
                    </div>
                )}
            </div>

            <div className="duration-shell">
                <p className="form-label">Video Duration</p>
                <div className="duration-card">
                    <span>🎬</span>
                    <div>
                        <strong>60 Seconds</strong>
                        <small>Detailed documentary narration with historical context.</small>
                    </div>
                </div>
            </div>

            <button type="submit" className="btn btn-primary btn-lg dashboard-submit" disabled={!selectedFile}>
                <Sparkles size={18} /> Generate Documentary
            </button>
        </form>
    );

    const renderProcessingArea = () => (
        <div className="dashboard-card processing-card">
            <LoaderCircle className="processing-spin" size={42} />
            <h3>Creating Your Documentary</h3>
            <p>{processingStatus}</p>

            <div className="processing-steps">
                {STEP_ITEMS.map((item, index) => (
                    <div
                        key={item.label}
                        className={`processing-step ${index === activeStep ? 'processing-step-active' : ''} ${index < activeStep ? 'processing-step-completed' : ''}`}
                    >
                        <span>{item.icon}</span>
                        <span>{item.label}</span>
                    </div>
                ))}
            </div>
        </div>
    );

    const renderResultArea = () => (
        <div className="dashboard-card result-card">
            <h3>Your Documentary is Ready</h3>
            <div className="result-layout">
                <div className="result-video-wrap">
                    <video controls className="result-video" src={normalizeVideoUrl(videoData?.video_url)} />
                </div>
                <div className="result-meta">
                    <h4>{videoData?.landmark_name || 'Landmark'}</h4>
                    {!!videoData?.is_unesco && <span className="unesco-chip">UNESCO World Heritage Site</span>}
                    <p>{videoData?.location ? `📍 ${videoData.location}` : '📍 Location detected'}</p>
                    <div className="script-box">
                        <strong>Script</strong>
                        <p>{videoData?.script || 'No script available.'}</p>
                    </div>
                </div>
            </div>

            <div className="result-actions">
                <button className="btn btn-primary" type="button" onClick={handleDownload}>
                    <Download size={16} /> Download Video
                </button>
                <button className="btn btn-outline" type="button" onClick={() => navigate(`/history/${videoData?.id}`)}>
                    🧠 View AI Analysis
                </button>
                <button className="btn btn-outline" type="button" onClick={resetAll}>
                    <RotateCcw size={16} /> Create Another
                </button>
            </div>
        </div>
    );

    const renderErrorArea = () => (
        <div className="dashboard-card error-card-shell">
            <h3>Something went wrong</h3>
            <p>{errorMessage || 'An unknown error occurred.'}</p>
            <button type="button" className="btn btn-primary" onClick={resetAll}>Try Again</button>
        </div>
    );

    return (
        <section className="dashboard-page-shell">
            <div className="container">
                <header className="dashboard-header">
                    <h1>Create Documentary</h1>
                    <p>Welcome back, {userDisplayName}. Upload a landmark photo and generate your narrated documentary.</p>
                </header>

                {errorMessage && phase === 'upload' && <p className="auth-error dashboard-error-inline">{errorMessage}</p>}

                {phase === 'upload' && renderUploadArea()}
                {phase === 'processing' && renderProcessingArea()}
                {phase === 'result' && renderResultArea()}
                {phase === 'error' && renderErrorArea()}
            </div>
        </section>
    );
};

export default Dashboard;
