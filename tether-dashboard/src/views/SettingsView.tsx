import { useEffect, useRef, useState } from 'react';
import { Eye, EyeOff, Save, Settings } from 'lucide-react';

type BackendMode = 'local' | 'relay';

const STORAGE_KEYS = {
  autoping: 'tether_autoping_enabled',
  staleHours: 'tether_stale_hours',
  backend: 'tether_backend',
  relayUrl: 'tether_relay_url',
  adminKey: 'tether_admin_key',
} as const;

const DEFAULT_STALE_HOURS = 24;

function readBoolean(key: string, fallback: boolean) {
  const value = window.localStorage.getItem(key);
  if (value === null) {
    return fallback;
  }
  return value === 'true';
}

function readNumber(key: string, fallback: number) {
  const value = Number(window.localStorage.getItem(key));
  if (!Number.isFinite(value)) {
    return fallback;
  }
  return Math.min(168, Math.max(1, Math.trunc(value)));
}

function readBackend() {
  const value = window.localStorage.getItem(STORAGE_KEYS.backend);
  return value === 'relay' ? 'relay' : 'local';
}

export function SettingsView() {
  const [autopingEnabled, setAutopingEnabled] = useState(false);
  const [staleHours, setStaleHours] = useState(DEFAULT_STALE_HOURS);
  const [backend, setBackend] = useState<BackendMode>('local');
  const [relayUrl, setRelayUrl] = useState('');
  const [adminKey, setAdminKey] = useState('');
  const [showAdminKey, setShowAdminKey] = useState(false);
  const [savedVisible, setSavedVisible] = useState(false);
  const timeoutRef = useRef<number | null>(null);

  useEffect(() => {
    setAutopingEnabled(readBoolean(STORAGE_KEYS.autoping, false));
    setStaleHours(readNumber(STORAGE_KEYS.staleHours, DEFAULT_STALE_HOURS));
    setBackend(readBackend());
    setRelayUrl(window.localStorage.getItem(STORAGE_KEYS.relayUrl) ?? '');
    setAdminKey(window.localStorage.getItem(STORAGE_KEYS.adminKey) ?? '');

    return () => {
      if (timeoutRef.current !== null) {
        window.clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  const handleSave = () => {
    window.localStorage.setItem(STORAGE_KEYS.autoping, String(autopingEnabled));
    window.localStorage.setItem(
      STORAGE_KEYS.staleHours,
      String(Math.min(168, Math.max(1, Math.trunc(staleHours || DEFAULT_STALE_HOURS)))),
    );
    window.localStorage.setItem(STORAGE_KEYS.backend, backend);
    window.localStorage.setItem(STORAGE_KEYS.relayUrl, relayUrl.trim());
    window.localStorage.setItem(STORAGE_KEYS.adminKey, adminKey);

    setSavedVisible(true);
    if (timeoutRef.current !== null) {
      window.clearTimeout(timeoutRef.current);
    }
    timeoutRef.current = window.setTimeout(() => {
      setSavedVisible(false);
    }, 2000);
  };

  return (
    <div className="w-full max-w-5xl mx-auto p-6 pb-12 flex flex-col gap-8">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold mb-1">Settings</h1>
          <p className="text-[#8892b0] text-sm">Client-side dashboard controls for local workflows and relay access.</p>
        </div>
        <div className="hidden sm:flex items-center gap-2 rounded-lg border border-[#ffffff14] bg-[#0f111a] px-3 py-2 text-xs text-[#8892b0]">
          <Settings className="w-4 h-4 text-[#00f2ff]" />
          Stored in localStorage
        </div>
      </div>

      <div className="bg-[#0f111a] border border-[#ffffff14] rounded-xl p-6 flex flex-col gap-8">
        <section className="flex flex-col gap-3">
          <div>
            <h2 className="text-base font-semibold text-white">Autonomous Mode</h2>
            <p className="text-sm text-[#8892b0]">Requires ping daemon running. See <code>scripts/install_services.sh</code>.</p>
          </div>
          <label className="flex items-center justify-between gap-4 rounded-lg border border-[#ffffff14] bg-[#05060a] px-4 py-3">
            <div>
              <div className="text-sm font-medium text-white">Autonomous Mode</div>
              <div className="text-xs text-[#8892b0]">Agents wake each other automatically on new messages.</div>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={autopingEnabled}
              onClick={() => setAutopingEnabled((value) => !value)}
              className={`relative h-7 w-12 rounded-full border transition-colors ${
                autopingEnabled
                  ? 'border-[#00f2ff] bg-[#00f2ff]/20'
                  : 'border-[#ffffff14] bg-[#ffffff0d]'
              }`}
            >
              <span
                className={`absolute top-1 h-5 w-5 rounded-full bg-white transition-transform ${
                  autopingEnabled ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </label>
        </section>

        <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="flex flex-col gap-3">
            <div>
              <h2 className="text-base font-semibold text-white">Stale after (hours)</h2>
              <p className="text-sm text-[#8892b0]">Maps to <code>TETHER_STALE_HOURS</code>. This does not update your environment file.</p>
            </div>
            <div className="rounded-lg border border-[#ffffff14] bg-[#05060a] px-4 py-3 flex flex-col gap-2">
              <label htmlFor="stale-hours" className="text-sm font-medium text-white">Stale after (hours)</label>
              <input
                id="stale-hours"
                type="number"
                min={1}
                max={168}
                step={1}
                value={staleHours}
                onChange={(event) => setStaleHours(Number(event.target.value))}
                className="w-full rounded-lg border border-[#ffffff14] bg-[#0b0d14] px-3 py-2 text-sm text-white outline-none focus:border-[#00f2ff]"
              />
            </div>
          </div>

          <div className="flex flex-col gap-3">
            <div>
              <h2 className="text-base font-semibold text-white">Backend</h2>
              <p className="text-sm text-[#8892b0]">Choose whether the dashboard should point at a local runtime or relay.</p>
            </div>
            <div className="rounded-lg border border-[#ffffff14] bg-[#05060a] px-4 py-3 flex flex-col gap-3">
              <label className="flex items-center gap-3 text-sm text-white">
                <input
                  type="radio"
                  name="backend"
                  checked={backend === 'local'}
                  onChange={() => setBackend('local')}
                  className="h-4 w-4 accent-[#00f2ff]"
                />
                TetherLite (local)
              </label>
              <label className="flex items-center gap-3 text-sm text-white">
                <input
                  type="radio"
                  name="backend"
                  checked={backend === 'relay'}
                  onChange={() => setBackend('relay')}
                  className="h-4 w-4 accent-[#00f2ff]"
                />
                Tether Cloud (relay)
              </label>
              {backend === 'relay' ? (
                <div className="flex flex-col gap-2">
                  <label htmlFor="relay-url" className="text-sm font-medium text-white">Relay URL</label>
                  <input
                    id="relay-url"
                    type="text"
                    value={relayUrl}
                    onChange={(event) => setRelayUrl(event.target.value)}
                    placeholder="https://relay.example.com"
                    className="w-full rounded-lg border border-[#ffffff14] bg-[#0b0d14] px-3 py-2 text-sm text-white outline-none focus:border-[#00f2ff]"
                  />
                </div>
              ) : null}
            </div>
          </div>
        </section>

        <section className="flex flex-col gap-3">
          <div>
            <h2 className="text-base font-semibold text-white">Admin Key</h2>
            <p className="text-sm text-[#8892b0]">Never sent to the server. Used client-side for admin UI only.</p>
          </div>
          <div className="rounded-lg border border-[#ffffff14] bg-[#05060a] px-4 py-3 flex flex-col gap-2">
            <label htmlFor="admin-key" className="text-sm font-medium text-white">Admin Key</label>
            <div className="flex items-center gap-2">
              <input
                id="admin-key"
                type={showAdminKey ? 'text' : 'password'}
                value={adminKey}
                onChange={(event) => setAdminKey(event.target.value)}
                className="w-full rounded-lg border border-[#ffffff14] bg-[#0b0d14] px-3 py-2 text-sm text-white outline-none focus:border-[#00f2ff]"
              />
              <button
                type="button"
                onClick={() => setShowAdminKey((value) => !value)}
                className="shrink-0 rounded-lg border border-[#ffffff14] bg-[#0b0d14] px-3 py-2 text-[#8892b0] hover:text-white transition-colors"
                aria-label={showAdminKey ? 'Hide admin key' : 'Show admin key'}
              >
                {showAdminKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>
        </section>

        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pt-2">
          <div
            className={`text-sm transition-opacity ${
              savedVisible ? 'opacity-100 text-[#00ff88]' : 'opacity-0 pointer-events-none'
            }`}
            aria-live="polite"
          >
            Saved.
          </div>
          <button
            type="button"
            onClick={handleSave}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-[#00f2ff] px-4 py-2 text-sm font-semibold text-[#05060a] hover:bg-[#6cf7ff] transition-colors"
          >
            <Save className="w-4 h-4" />
            Save Settings
          </button>
        </div>
      </div>
    </div>
  );
}
