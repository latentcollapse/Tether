import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { api } from '../api/client';
import { UI_STRINGS } from '../utils/constants';
import { Cpu } from 'lucide-react';
import { LoadingSpinner } from '../components/shared/LoadingSpinner';

export function LoginView() {
  const [key, setKey] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { token, login } = useAuthStore();
  const navigate = useNavigate();

  useEffect(() => {
    if (token) {
      navigate('/');
    }
  }, [navigate, token]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    
    if (!key.trim()) return;

    setLoading(true);
    try {
      const res = await api.login(key);
      login(res.token, res.isAdmin, false);
      navigate('/');
    } catch (err: any) {
      setError(UI_STRINGS.INVALID_KEY);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full flex flex-col items-center justify-center bg-[#05060a] text-[#e0e6ed] px-4">
      <div className="w-full max-w-sm flex flex-col items-center">
        <Cpu className="w-12 h-12 text-[#00f2ff] mb-6" />
        <h1 className="text-2xl font-semibold tracking-tight mb-2">Tether</h1>
        <p className="text-[#8892b0] mb-8">{UI_STRINGS.TAGLINE}</p>

        <form onSubmit={handleSubmit} className="w-full bg-[#0f111a] border border-[#ffffff14] rounded-2xl p-6 shadow-xl stat-card-gradient relative overflow-hidden">
          <div className="mb-4">
            <label htmlFor="key" className="block text-sm font-medium text-[#8892b0] mb-1.5">
              API Key
            </label>
            <input
              id="key"
              type="password"
              value={key}
              onChange={(e) => setKey(e.target.value)}
              placeholder="tk_live_..."
              className={`w-full bg-[#05060a] border ${error ? 'border-[#ef4444]' : 'border-[#ffffff14]'} focus:border-[#00f2ff] rounded-lg px-3 py-2 font-mono text-sm outline-none transition-colors placeholder:text-[#8892b0]`}
              autoFocus
            />
            {error && <p className="text-[#ef4444] text-xs mt-1.5">{error}</p>}
          </div>

          <button
            type="submit"
            disabled={loading || !key.trim()}
            className="w-full bg-[#00f2ff] hover:bg-[#00d1d1] disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium py-2 rounded-lg transition-colors flex items-center justify-center h-10"
          >
            {loading ? <LoadingSpinner className="text-white" /> : UI_STRINGS.CONNECT}
          </button>
        </form>

        <a
          href="https://github.com/latentcollapse/Tether"
          target="_blank"
          rel="noreferrer"
          className="text-[#8892b0] text-xs mt-6 hover:text-[#e0e6ed] transition-colors"
        >
          {UI_STRINGS.NO_KEY_HINT}
        </a>
      </div>
    </div>
  );
}
