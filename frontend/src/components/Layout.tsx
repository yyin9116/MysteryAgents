import { Ghost, Settings, SlidersHorizontal } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useI18n } from '../hooks/useI18n';

interface LayoutProps {
    children: React.ReactNode;
    wide?: boolean;
}

const Layout: React.FC<LayoutProps> = ({ children, wide = false }) => {
    const { t } = useI18n();

    return (
        <div className="min-h-screen bg-background text-text selection:bg-primary/30">
            <header className="sticky top-0 z-50 glass-dark border-b border-white/5 py-4 px-6 mb-8">
                <div className="max-w-7xl mx-auto flex items-center justify-between">
                    <Link to="/" className="flex items-center space-x-3 group">
                        <div className="p-2 bg-primary/20 rounded-xl group-hover:bg-primary/30 transition-colors">
                            <Ghost className="w-8 h-8 text-primary" />
                        </div>
                        <div>
                            <h1 className="text-xl font-bold tracking-tight bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
                                {t.app.title}
                            </h1>
                            <p className="text-xs text-text-muted">{t.app.subtitle}</p>
                        </div>
                    </Link>
                    <nav className="flex items-center space-x-4">
                        <Link
                            to="/settings"
                            className="hidden sm:flex items-center gap-2 px-4 py-2 rounded-full border border-white/10 text-sm text-text-muted hover:text-primary hover:border-primary/40 hover:bg-white/5 transition-all"
                        >
                            <SlidersHorizontal className="w-4 h-4" />
                            Model Configs
                        </Link>
                        <Link
                            to="/settings"
                            className="p-2 hover:bg-white/5 rounded-xl transition-all hover:scale-110 active:scale-95 text-text-muted hover:text-primary border border-transparent hover:border-primary/20"
                        >
                            <Settings className="w-6 h-6" />
                        </Link>
                    </nav>
                </div>
            </header>

            <main className={`${wide ? 'max-w-[1400px]' : 'max-w-7xl'} mx-auto px-6 pb-20`}>
                {children}
            </main>

            <footer className="py-8 px-6 border-t border-white/5 text-center text-sm text-text-muted">
                &copy; 2025 {t.app.title}. Powered by Advanced Agentic Coding.
            </footer>
        </div>
    );
};

export default Layout;
