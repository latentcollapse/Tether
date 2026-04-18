import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { useEffect } from 'react';
import { Layout } from './components/layout/Layout';
import { LoadingSpinner } from './components/shared/LoadingSpinner';
import { LoginView } from './views/LoginView';
import { NetworkView } from './views/NetworkView';
import { HandleBrowserView } from './views/HandleBrowserView';
import { ConnectionView } from './views/ConnectionView';
import { UsageView } from './views/UsageView';
import { MessagesView } from './views/MessagesView';
import { api } from './api/client';
import { useAuthStore } from './store/authStore';

export default function App() {
  const {
    token,
    isValidating,
    hasInitialized,
    login,
    setLocalMode,
    setInitialized,
    setValidating,
  } = useAuthStore();

  useEffect(() => {
    if (hasInitialized || token) {
      if (!hasInitialized) {
        setInitialized(true);
      }
      return;
    }

    let cancelled = false;

    const bootstrap = async () => {
      setValidating(true);
      try {
        const health = await api.getHealth();
        if (!cancelled) {
          if (health?.mode === 'lite') {
            login('local-mode', false, true);
            return;
          }
          setLocalMode(false);
          setInitialized(true);
        }
      } catch {
        if (!cancelled) {
          login('local-mode', false, true);
        }
      } finally {
        if (!cancelled) {
          setValidating(false);
        }
      }
    };

    void bootstrap();

    return () => {
      cancelled = true;
    };
  }, [hasInitialized, login, setInitialized, setLocalMode, setValidating, token]);

  if (!hasInitialized || isValidating) {
    return (
      <div className="min-h-screen w-full flex items-center justify-center bg-[#05060a] text-[#e0e6ed]">
        <LoadingSpinner className="w-8 h-8 text-[#00f2ff]" />
      </div>
    );
  }

  return (
    <Router>
      <Routes>
        <Route path="/login" element={<LoginView />} />
        <Route element={<Layout />}>
          <Route path="/" element={<NetworkView />} />
          <Route path="/messages" element={<MessagesView />} />
          <Route path="/connection" element={<ConnectionView />} />
          <Route path="/handles" element={<HandleBrowserView />} />
          <Route path="/usage" element={<UsageView />} />
        </Route>
      </Routes>
    </Router>
  );
}
