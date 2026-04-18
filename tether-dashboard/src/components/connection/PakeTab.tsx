import React, { useState } from 'react';
import { Shield, Link2, KeyRound } from 'lucide-react';
import { cn } from '../../utils/cn';

export const PakeTab: React.FC = () => {
  const [passphrase, setPassphrase] = useState('');
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<'idle' | 'connecting' | 'success'>('idle');

  const handleConnect = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!passphrase) return;

    setLoading(true);
    setStatus('connecting');

    // Simulate key exchange
    setTimeout(() => {
      setLoading(false);
      setStatus('success');
      setPassphrase(''); // Clear on success
    }, 1500);
  };

  return (
    <div className="p-8 max-w-2xl h-full flex flex-col">
      <div className="mb-8">
        <h2 className="text-xl font-semibold mb-2 flex items-center gap-2">
          <Shield className="w-5 h-5 text-[#00f2ff]" />
          PAKE Direct Connection
        </h2>
        <p className="text-[#8892b0] leading-relaxed">
          Establish a secure, direct connection to another agent over LAN or WAN using a shared passphrase via Password-Authenticated Key Exchange.
        </p>
      </div>

      <form onSubmit={handleConnect} className="flex-1">
        <div className="bg-[#05060a] border border-[#ffffff14] rounded-xl p-6 relative">
          <label className="block text-sm font-medium text-[#8892b0] mb-2">
            Shared Passphrase
          </label>
          <div className="flex gap-4">
            <div className="relative flex-1">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <KeyRound className="h-4 w-4 text-[#8892b0]" />
              </div>
              <input
                type="text"
                value={passphrase}
                onChange={e => setPassphrase(e.target.value)}
                placeholder="Enter connection passphrase..."
                className="w-full bg-[#0f111a] border border-[#ffffff14] focus:border-[#00f2ff] rounded-lg pl-10 pr-4 py-3 font-mono text-sm outline-none transition-colors text-[#e0e6ed] placeholder:text-[#8892b0]/50"
                disabled={loading || status === 'success'}
                required
              />
            </div>
            <button
              type="submit"
              disabled={loading || status === 'success' || !passphrase}
              className={cn(
                "px-6 py-3 rounded-lg font-semibold flex items-center gap-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-[#05060a]",
                status === 'success' ? "bg-[#22c55e]" : "bg-[#00f2ff] hover:bg-[#00d1d1]"
              )}
            >
              <Link2 className="w-4 h-4" />
              {loading ? 'Exchanging keys...' : status === 'success' ? 'Connected' : 'Connect'}
            </button>
          </div>
          
          <div className="mt-6 p-4 rounded-lg border border-[#ffffff14] bg-[#0f111a] text-xs text-[#8892b0]">
            <strong className="text-[#e0e6ed] block mb-1">LAN vs WAN Routing</strong>
            The relay will automatically attempt direct local routing if the target agent appears on the same subnet. If direct discovery fails, it falls back to secure NAT traversal.
          </div>
        </div>
      </form>
      
      {status === 'success' && (
        <div className="mt-6 flex flex-col items-center">
          <p className="text-[#00f2ff] text-sm flex items-center gap-2 font-medium">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#00f2ff] opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-[#00f2ff] shadow-[0_0_8px_#00f2ff]"></span>
            </span>
            Secure tunnel established successfully.
          </p>
          <button 
            type="button"
            className="mt-4 text-[#8892b0] hover:text-[#e0e6ed] text-xs underline"
            onClick={() => setStatus('idle')}
          >
            Start another connection
          </button>
        </div>
      )}
    </div>
  );
};
