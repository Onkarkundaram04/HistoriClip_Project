import { Film } from 'lucide-react';

const Footer = () => {
    return (
        <footer className="site-footer">
            <div className="container">
                <div className="site-footer-inner">
                    <div className="site-footer-brand">
                        <Film color="var(--primary)" size={24} />
                        <span className="site-footer-title">HistoriClip</span>
                        <span className="site-footer-tagline">
                            | AI-Powered Documentary Generation
                        </span>
                    </div>

                    <div className="site-footer-copy">
                        &copy; {new Date().getFullYear()} B.Tech Final Year Project. Premium Design Edition.
                    </div>
                </div>
            </div>
        </footer>
    );
};

export default Footer;
