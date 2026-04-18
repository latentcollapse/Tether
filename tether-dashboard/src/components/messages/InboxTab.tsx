import React, { useState } from 'react';
import { useInboxStore } from '../../store/inboxStore';
import { timeAgo, truncateHandle } from '../../utils/formatters';
import { Mail, MailOpen, CornerUpLeft, Check, X } from 'lucide-react';
import { cn } from '../../utils/cn';

export const InboxTab: React.FC = () => {
  const { messages, markRead, closeThread } = useInboxStore();
  const [expandedId, setExpandedId] = useState<string | null>(null);

  if (messages.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-[#8892b0]">
        <MailOpen className="w-12 h-12 mb-4 opacity-50" />
        <p>Your inbox is empty.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full divide-y divide-[#ffffff14] overflow-y-auto">
      {messages.map(msg => {
        const isExpanded = expandedId === msg.id;
        const isOpen = msg.status === 'open';

        return (
          <div 
            key={msg.id} 
            className={cn(
              "flex flex-col transition-colors border-l-[3px]",
              isOpen ? "border-[#00f2ff] bg-[#ffffff14]/5" : "border-transparent hover:bg-[#ffffff14]/5",
              isExpanded && "bg-[#ffffff14]/10 hover:bg-[#ffffff14]/10"
            )}
          >
            {/* Header row */}
            <div 
              className="flex items-center gap-4 px-4 py-3 cursor-pointer group"
              onClick={() => {
                setExpandedId(isExpanded ? null : msg.id);
                if (isOpen) markRead(msg.id);
              }}
            >
              <div className="w-48 shrink-0 font-medium truncate text-[#e0e6ed]">
                {msg.from}
              </div>
              
              <div className="flex-1 min-w-0 flex items-center gap-2">
                {msg.ticketId && (
                  <span className="px-2 py-0.5 rounded text-[10px] uppercase font-bold bg-[#7000ff]/20 text-[#7000ff] border border-[#7000ff]/30 shrink-0">
                    {msg.ticketId}
                  </span>
                )}
                <span className={cn("truncate", isOpen ? "text-white font-medium" : "text-[#8892b0]")}>
                  {msg.subject}
                </span>
                {!isExpanded && (
                  <span className="truncate text-[#8892b0]/50 text-sm ml-2">
                    - {msg.text.substring(0, 60)}...
                  </span>
                )}
              </div>

              <div className="hidden md:block shrink-0 px-2 py-1 bg-[#05060a] border border-[#ffffff14] rounded font-mono text-[11px] text-[#7000ff] opacity-0 group-hover:opacity-100 transition-opacity">
                {truncateHandle(msg.handle)}
              </div>

              <div className="w-24 shrink-0 text-right text-xs text-[#8892b0]">
                {timeAgo(msg.createdAt)}
              </div>
            </div>

            {/* Expanded inline content */}
            {isExpanded && (
              <div className="px-4 py-4 ml-[204px] mr-12 border-t border-[#ffffff14]/50">
                <div className="text-sm text-[#e0e6ed] whitespace-pre-wrap leading-relaxed mb-6 font-sans">
                  {msg.text}
                </div>
                
                <div className="flex items-center gap-3">
                  <button className="flex items-center gap-1.5 px-3 py-1.5 bg-[#00f2ff]/10 hover:bg-[#00f2ff]/20 text-[#00f2ff] text-xs font-semibold rounded transition-colors">
                    <CornerUpLeft className="w-3.5 h-3.5" />
                    Reply
                  </button>
                  {msg.status !== 'closed' && (
                    <button 
                      onClick={(e) => { e.stopPropagation(); closeThread(msg.id); }}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-[#ffffff14] hover:bg-[#ffffff14]/80 text-[#e0e6ed] text-xs font-medium rounded transition-colors"
                    >
                      <Check className="w-3.5 h-3.5" />
                      Mark Resolved
                    </button>
                  )}
                  <button 
                    onClick={(e) => { e.stopPropagation(); setExpandedId(null); }}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-transparent hover:bg-[#ffffff14] text-[#8892b0] text-xs font-medium rounded transition-colors ml-auto"
                  >
                    <X className="w-3.5 h-3.5" />
                    Close
                  </button>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};
