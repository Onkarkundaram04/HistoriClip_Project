import { useState, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Film, Moon, Sun } from 'lucide-react';
import { auth } from '../utils/auth';

const Navbar = ({ theme, onToggleTheme }) => {
    const [scrolled, setScrolled] = useState(false);
    const location = useLocation();
    const navigate = useNavigate();

    useEffect(() => {
        let rafId = null;

        const handleScroll = () => {
            if (rafId) {
                return;
            }

            rafId = window.requestAnimationFrame(() => {
                setScrolled(window.scrollY > 20);
                rafId = null;
            });
        };

        window.addEventListener('scroll', handleScroll);

        return () => {
            if (rafId) {
                window.cancelAnimationFrame(rafId);
            }
            window.removeEventListener('scroll', handleScroll);
        };
    }, []);

    const isHome = location.pathname === '/';
    const isLoggedIn = auth.isLoggedIn();
    const user = auth.getUser();

    const handleLogout = () => {
        auth.logout();
        navigate('/login', { replace: true });
    };

    return (
        <nav className={`navbar ${scrolled ? 'navbar-scrolled' : ''}`}>
            <div className="container navbar-inner">
                <Link to={isLoggedIn ? '/dashboard' : '/'} className="navbar-brand">
                    <Film size={28} color="var(--primary)" />
                    <span>Histori<span className="text-gradient">Clip</span></span>
                </Link>

                {!isLoggedIn && isHome && (
                    <div className="navbar-links">
                        <a href="#features">Features</a>
                        <a href="#how-it-works">How It Works</a>
                    </div>
                )}

                {isLoggedIn && (
                    <div className="navbar-links">
                        <Link to="/dashboard" className={location.pathname === '/dashboard' ? 'nav-link-active' : ''}>Create</Link>
                        <Link to="/history" className={location.pathname.startsWith('/history') ? 'nav-link-active' : ''}>My Videos</Link>
                    </div>
                )}

                <div className="navbar-actions">
                    <button
                        type="button"
                        className="theme-toggle-btn"
                        onClick={onToggleTheme}
                        aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
                        title={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
                    >
                        {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
                    </button>

                    {isLoggedIn ? (
                        <>
                            <span className="nav-user-name">{user?.name || user?.email || 'User'}</span>
                            <button type="button" className="btn btn-outline nav-logout-btn" onClick={handleLogout}>Logout</button>
                        </>
                    ) : (
                        <>
                            <Link to="/login" className="btn btn-ghost">Log In</Link>
                            <Link to="/signup" className="btn btn-primary">Get Started</Link>
                        </>
                    )}
                </div>
            </div>
        </nav>
    );
};

export default Navbar;
