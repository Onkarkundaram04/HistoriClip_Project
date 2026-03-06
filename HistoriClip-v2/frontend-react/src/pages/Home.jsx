import { Link } from 'react-router-dom';
import { Camera, Video, Zap, BookOpen, Image as ImageIcon, Mic, Film, ShieldCheck, ArrowRight } from 'lucide-react';

const Home = () => {
    const features = [
        { icon: <Zap size={36} />, title: 'Vision AI', desc: 'Automatically detects landmarks using Google Cloud Vision with precise GPS metadata extraction.' },
        { icon: <BookOpen size={36} />, title: 'Research Engine', desc: 'Fetches UNESCO data, verifies Wikipedia facts, and generates compelling script narratives.' },
        { icon: <ImageIcon size={36} />, title: 'Image Generation', desc: 'Creates contextual visuals with advanced Stable Diffusion AI models.' },
        { icon: <Mic size={36} />, title: 'Voice Narration', desc: 'Studio-quality text-to-speech voiceovers with natural cadence and tone.' },
        { icon: <Film size={36} />, title: 'Video Editor', desc: 'Assembles imagery, voiceovers, effects, and transitions into a polished cinematic render.' },
        { icon: <ShieldCheck size={36} />, title: 'UNESCO Verified', desc: 'Cross-references your location against the official UNESCO World Heritage database.' }
    ];

    return (
        <div className="home-page">
            <section className="hero-section">
                <div className="hero-orb hero-orb-left" aria-hidden="true" />
                <div className="hero-orb hero-orb-right" aria-hidden="true" />

                <div className="container hero-grid">
                    <div className="hero-copy animate-fade-in">
                        <div className="hero-badge">
                            AI-Powered Documentation
                        </div>

                        <h1 className="hero-title">
                            Transform Photos into<br />
                            <span className="text-gradient">Documentary Videos</span>
                        </h1>

                        <p className="hero-subtitle">
                            Upload a landmark photo and let AI create a professional 30-second
                            narrated documentary with stunning visuals and historical facts.
                        </p>

                        <div className="hero-actions">
                            <Link to="/signup" className="btn btn-primary btn-lg">
                                <Zap size={20} /> Start Creating Free
                            </Link>
                            <a href="#how-it-works" className="btn btn-outline btn-lg">
                                Watch Demo
                            </a>
                        </div>

                        <div className="hero-stats">
                            <div className="hero-stat-item">
                                <span>1000+</span>
                                <small>UNESCO Sites</small>
                            </div>
                            <div className="hero-stat-item">
                                <span>30s</span>
                                <small>Video Duration</small>
                            </div>
                            <div className="hero-stat-item">
                                <span>AI</span>
                                <small>Powered</small>
                            </div>
                        </div>
                    </div>

                    <div className="hero-visual animate-fade-in">
                        <div className="glass-card hero-flow-card">
                            <div className="flow-item">
                                <Camera size={56} />
                                <p>Upload Landmark Photo</p>
                                <small>JPG, PNG, WebP</small>
                            </div>

                            <div className="flow-arrow">
                                <ArrowRight size={22} />
                            </div>

                            <div className="flow-item">
                                <Video size={56} />
                                <p>Get Documentary Video</p>
                                <small>HD 1080p, Narrated</small>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            <section id="features" className="features-section">
                <div className="container">
                    <div className="section-head">
                        <h2>Powered by <span className="text-gradient">Advanced AI</span></h2>
                        <p>Six machine learning modules work together to write, narrate, and direct your documentary.</p>
                    </div>

                    <div className="features-grid">
                        {features.map((feature, i) => (
                            <article key={i} className="glass-card feature-card">
                                <div className="feature-icon">{feature.icon}</div>
                                <h3>{feature.title}</h3>
                                <p>{feature.desc}</p>
                            </article>
                        ))}
                    </div>
                </div>
            </section>

            <section id="how-it-works" className="steps-section">
                <div className="container">
                    <div className="section-head">
                        <h2>How It <span className="text-gradient">Works</span></h2>
                        <p>From photo to final render in three effortless steps.</p>
                    </div>

                    <div className="steps-grid">
                        {[
                            { num: '01', title: 'Upload Photo', desc: 'Take or upload an image of any famous historical landmark.' },
                            { num: '02', title: 'AI Processing', desc: 'The engine identifies, researches, scripts, and generates visuals.' },
                            { num: '03', title: 'Get Video', desc: 'Download your professional, ready-to-share documentary video.' }
                        ].map((step, i) => (
                            <article key={i} className="step-card">
                                <div className="step-badge">{step.num}</div>
                                <h3>{step.title}</h3>
                                <p>{step.desc}</p>
                            </article>
                        ))}
                    </div>
                </div>
            </section>

            <section className="cta-section">
                <div className="container cta-wrap">
                    <h2>Ready to Create Your First Documentary?</h2>
                    <p>Join creators turning travel photos into captivating historical stories in seconds.</p>
                    <Link to="/signup" className="btn btn-primary btn-lg">
                        Start Creating For Free
                        <ArrowRight size={20} />
                    </Link>
                </div>
            </section>
        </div>
    );
};

export default Home;
