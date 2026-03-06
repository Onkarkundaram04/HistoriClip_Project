import { useEffect, useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import './App.css';
import Navbar from './components/Navbar';
import Footer from './components/Footer';
import Home from './pages/Home';
import Login from './pages/Login';
import Signup from './pages/Signup';
import Dashboard from './pages/Dashboard';
import History from './pages/History';
import VideoDetail from './pages/VideoDetail';
import { auth } from './utils/auth';

function ProtectedRoute({ children }) {
  if (!auth.isLoggedIn()) {
    return <Navigate to="/login" replace />;
  }

  return children;
}

function AppLayout() {
  const [theme, setTheme] = useState(() => {
    try {
      return localStorage.getItem('historiclip-theme') || 'dark';
    } catch {
      return 'dark';
    }
  });

  const location = useLocation();
  const isAuthPage = location.pathname === '/login' || location.pathname === '/signup';

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    try {
      localStorage.setItem('historiclip-theme', theme);
    } catch {
      // no-op when storage is unavailable
    }
  }, [theme]);

  const handleThemeToggle = () => {
    setTheme((prevTheme) => (prevTheme === 'dark' ? 'light' : 'dark'));
  };

  return (
    <div className="app-container">
      <Navbar theme={theme} onToggleTheme={handleThemeToggle} />
      <main className={isAuthPage ? 'main-content auth-main' : 'main-content'}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />
          <Route
            path="/dashboard"
            element={(
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            )}
          />
          <Route
            path="/history"
            element={(
              <ProtectedRoute>
                <History />
              </ProtectedRoute>
            )}
          />
          <Route
            path="/history/:id"
            element={(
              <ProtectedRoute>
                <VideoDetail />
              </ProtectedRoute>
            )}
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
      {!isAuthPage && <Footer />}
    </div>
  );
}

function App() {
  return (
    <Router>
      <AppLayout />
    </Router>
  );
}

export default App;
