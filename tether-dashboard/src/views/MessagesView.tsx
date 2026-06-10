import React, { useState, useEffect } from 'react';
import { InboxTab } from '../components/messages/InboxTab';
import { ComposeTab } from '../components/messages/ComposeTab';
import { HandleBrowserView } from './HandleBrowserView';
import { Inbox, PenSquare, Search } from 'lucide-react';
import { useInboxStore } from '../store/inboxStore';
import { api } from '../api/client';
import { cn } from '../utils/cn';

export const MessagesView: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'inbox' | 'compose' | 'handles'>('inbox');
  const { setMessages, unreadCount } = useInboxStore();

  useEffect(() => {
    // Initial fetch
    api.getInbox().then(setMessages).catch(console.error);

    // Polling simulation every 5s
    const interval = setInterval(() => {
      api.getInbox().then(setMessages).catch(console.error);
    }, 5000);

    return () => clearInterval(interval);
  }, [setMessages]);

  return (
    <div className="flex flex-col h-full w-full">
      {/* Header / Tabs */}
      <div className="h-[80px] shrink-0 border-b border-[#ffffff14] px-6 flex items-end gap-6 bg-[#05060a]">
        <button
          onClick={() => setActiveTab('inbox')}
          className={cn(
            "pb-4 flex items-center gap-2 border-b-2 transition-colors relative",
            activeTab === 'inbox' 
              ? "border-[#00f2ff] text-[#00f2ff]" 
              : "border-transparent text-[#8892b0] hover:text-[#e0e6ed]"
          )}
        >
          <Inbox className="w-4 h-4" />
          <span className="font-medium text-sm">Inbox</span>
          {unreadCount > 0 && (
            <span className="flex items-center justify-center bg-[#00f2ff] text-[#05060a] text-[10px] font-bold h-4 min-w-4 px-1 rounded-full absolute -top-1 -right-4">
              {unreadCount}
            </span>
          )}
        </button>

        <button
          onClick={() => setActiveTab('compose')}
          className={cn(
            "pb-4 flex items-center gap-2 border-b-2 transition-colors",
            activeTab === 'compose' 
              ? "border-[#00f2ff] text-[#00f2ff]" 
              : "border-transparent text-[#8892b0] hover:text-[#e0e6ed]"
          )}
        >
          <PenSquare className="w-4 h-4" />
          <span className="font-medium text-sm">Compose</span>
        </button>

        <button
          onClick={() => setActiveTab('handles')}
          className={cn(
            "pb-4 flex items-center gap-2 border-b-2 transition-colors",
            activeTab === 'handles' 
              ? "border-[#00f2ff] text-[#00f2ff]" 
              : "border-transparent text-[#8892b0] hover:text-[#e0e6ed]"
          )}
        >
          <Search className="w-4 h-4" />
          <span className="font-medium text-sm">Search Handles</span>
        </button>
      </div>

      {/* Content Area */}
      <div className="flex-1 overflow-hidden bg-[#0f111a] m-6 border border-[#ffffff14] rounded-2xl stat-card-gradient relative shadow-xl">
        {activeTab === 'inbox' ? (
          <InboxTab />
        ) : activeTab === 'compose' ? (
          <ComposeTab />
        ) : (
          <HandleBrowserView />
        )}
      </div>
    </div>
  );
};
