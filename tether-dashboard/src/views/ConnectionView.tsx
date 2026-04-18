import React, { useState } from 'react';
import { PakeTab } from '../components/connection/PakeTab';
import { KeyManager } from '../components/keys/KeyManager';
import { Shield, Key } from 'lucide-react';
import { cn } from '../utils/cn';

export const ConnectionView: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'pake' | 'network_keys'>('pake');

  return (
    <div className="flex flex-col h-full w-full">
      {/* Header / Tabs */}
      <div className="h-[80px] shrink-0 border-b border-[#ffffff14] px-6 flex items-end gap-6 bg-[#05060a]">
        <button
          onClick={() => setActiveTab('pake')}
          className={cn(
            "pb-4 flex items-center gap-2 border-b-2 transition-colors relative",
            activeTab === 'pake' 
              ? "border-[#00f2ff] text-[#00f2ff]" 
              : "border-transparent text-[#8892b0] hover:text-[#e0e6ed]"
          )}
        >
          <Shield className="w-4 h-4" />
          <span className="font-medium text-sm">PAKE</span>
        </button>

        <button
          onClick={() => setActiveTab('network_keys')}
          className={cn(
            "pb-4 flex items-center gap-2 border-b-2 transition-colors",
            activeTab === 'network_keys' 
              ? "border-[#00f2ff] text-[#00f2ff]" 
              : "border-transparent text-[#8892b0] hover:text-[#e0e6ed]"
          )}
        >
          <Key className="w-4 h-4" />
          <span className="font-medium text-sm">Network keys</span>
        </button>
      </div>

      {/* Content Area */}
      <div className="flex-1 overflow-hidden m-6 relative">
        {activeTab === 'pake' ? (
          <div className="h-full bg-[#0f111a] border border-[#ffffff14] rounded-2xl stat-card-gradient relative shadow-xl overflow-y-auto">
            <PakeTab />
          </div>
        ) : (
          <div className="h-full overflow-y-auto pb-4">
            <KeyManager />
          </div>
        )}
      </div>
    </div>
  );
};
