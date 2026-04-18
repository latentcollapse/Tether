import { useState } from 'react';
import { AgentGraph } from '../components/network/AgentGraph';
import { MessageFeed } from '../components/feed/MessageFeed';
import { RegisterTab } from '../components/network/RegisterTab';
import { Network, Plus } from 'lucide-react';
import { cn } from '../utils/cn';

export function NetworkView() {
  const [activeTab, setActiveTab] = useState<'network' | 'register'>('network');

  return (
    <div className="flex flex-col h-full w-full">
      {/* Header / Tabs */}
      <div className="h-[80px] shrink-0 border-b border-[#ffffff14] px-6 flex items-end gap-6 bg-[#05060a]">
        <button
          onClick={() => setActiveTab('network')}
          className={cn(
            "pb-4 flex items-center gap-2 border-b-2 transition-colors relative",
            activeTab === 'network' 
              ? "border-[#00f2ff] text-[#00f2ff]" 
              : "border-transparent text-[#8892b0] hover:text-[#e0e6ed]"
          )}
        >
          <Network className="w-4 h-4" />
          <span className="font-medium text-sm">Network Graph</span>
        </button>

        <button
          onClick={() => setActiveTab('register')}
          className={cn(
            "pb-4 flex items-center gap-2 border-b-2 transition-colors",
            activeTab === 'register' 
              ? "border-[#00f2ff] text-[#00f2ff]" 
              : "border-transparent text-[#8892b0] hover:text-[#e0e6ed]"
          )}
        >
          <Plus className="w-4 h-4" />
          <span className="font-medium text-sm">Register</span>
        </button>
      </div>

      {/* Content Area */}
      <div className="flex-1 min-h-0 flex relative">
        {activeTab === 'network' ? (
          <>
            <div className="flex-1 relative">
              <AgentGraph />
            </div>
            
            <div className="w-80 md:w-96 shrink-0 relative flex flex-col hidden sm:flex border-l border-[#ffffff14]">
              <MessageFeed />
            </div>
          </>
        ) : (
          <div className="flex-1 overflow-y-auto px-6">
            <RegisterTab />
          </div>
        )}
      </div>
    </div>
  );
}
