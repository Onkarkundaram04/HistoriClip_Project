import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Eye, EyeOff, Film, Mail, Lock } from 'lucide-react';
import { api } from '../utils/api';
import { auth } from '../utils/auth';

const Login = () => {
    const navigate = useNavigate();
    const [formData, setFormData] = useState({
        email: '',
        password: ''
    });
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [showPassword, setShowPassword] = useState(false);

    useEffect(() => {
        if (auth.isLoggedIn()) {
            navigate('/dashboard', { replace: true });
        }
    }, [navigate]);

    const handleSubmit = async (e) => {
        e.preventDefault();

        if (!formData.email.trim() || !formData.password) {
            setError('Please fill in all fields.');
            return;
        }

        setError('');
        setLoading(true);

        try {
            const response = await api.post('/auth/login', {
                email: formData.email.trim(),
                password: formData.password
            });

            auth.setToken(response.data.token);
            auth.setUser(response.data.user);
            navigate('/dashboard', { replace: true });
        } catch (requestError) {
            setError(requestError.message || 'Login failed. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <section className="auth-page">
            <div className="auth-orb auth-orb-left" aria-hidden="true" />
            <div className="auth-orb auth-orb-right" aria-hidden="true" />

            <div className="auth-card-wrap animate-fade-in">
                <div className="auth-head">
                    <Link to="/" className="auth-brand">
                        <div className="auth-brand-icon">
                            <Film size={30} />
                        </div>
                        <span>Histori<span className="text-gradient">Clip</span></span>
                    </Link>
                    <h1>Welcome back</h1>
                    <p>Log in to your account.</p>
                </div>

                <div className="glass-card auth-card">
                    <form onSubmit={handleSubmit} className="auth-form">
                        {error && <p className="auth-error">{error}</p>}

                        <div className="form-group">
                            <label className="form-label">Email Address</label>
                            <div className="input-wrap">
                                <div className="input-icon" aria-hidden="true">
                                    <Mail size={18} />
                                </div>
                                <input
                                    type="email"
                                    required
                                    className="form-input"
                                    placeholder="you@example.com"
                                    value={formData.email}
                                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                                />
                            </div>
                        </div>

                        <div className="form-group">
                            <div className="auth-field-head">
                                <label className="form-label">Password</label>
                                <button type="button" className="auth-link auth-link-btn">Forgot password?</button>
                            </div>
                            <div className="input-wrap">
                                <div className="input-icon" aria-hidden="true">
                                    <Lock size={18} />
                                </div>
                                <input
                                    type={showPassword ? 'text' : 'password'}
                                    required
                                    className="form-input password-input"
                                    placeholder="••••••••"
                                    value={formData.password}
                                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                                />
                                <button
                                    type="button"
                                    className="password-toggle-btn"
                                    onClick={() => setShowPassword((previous) => !previous)}
                                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                                    title={showPassword ? 'Hide password' : 'Show password'}
                                >
                                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                                </button>
                            </div>
                        </div>

                        <button type="submit" className="btn btn-primary auth-submit" disabled={loading}>
                            {loading ? 'Signing In...' : 'Sign In'} <ArrowRight className="auth-submit-icon" />
                        </button>
                    </form>

                    <div className="auth-footer-text">
                        <p>
                            Don't have an account?{' '}
                            <Link to="/signup" className="auth-link auth-link-strong">
                                Sign up
                            </Link>
                        </p>
                    </div>
                </div>
            </div>
        </section>
    );
};

// Extracted ArrowRight to avoid extra import in this file
const ArrowRight = ({ className }) => (
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}><path d="M5 12h14" /><path d="m12 5 7 7-7 7" /></svg>
);

export default Login;
