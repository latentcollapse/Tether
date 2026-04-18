import React from 'react';
import { CopyButton } from '../shared/CopyButton';
import { formatTime, truncateHandle } from '../../utils/formatters';
import { FeedItem as FeedItemType } from '../../types/message';

interface FeedItemProps {
  item: FeedItemType;
  onClick: () => void;
}

export const FeedItem: React.FC<FeedItemProps> = ({ item, onClick }) => {
  return (
    <div 
      className="flex items-center gap-3 px-4 py-2 hover:bg-[#0f111a] transition-colors cursor-pointer border-b border-[#ffffff14]/50 last:border-0 group"
      onClick={onClick}
    >
      <span className="text-xs text-[#8892b0] font-mono shrink-0 w-16">
        {formatTime(item.timestamp)}
      </span>
      
      <div className="flex flex-col flex-1 min-w-0">
        <div className="flex items-center gap-2 text-xs text-[#8892b0] truncate mb-0.5">
          <span className="truncate">{item.from.split('@')[0]}</span>
          <span>→</span>
          <span className="truncate">{item.to.split('@')[0]}</span>
        </div>
        
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-[#7000ff]">
            {truncateHandle(item.handle)}
          </span>
          <CopyButton text={item.handle} iconOnly className="opacity-0 group-hover:opacity-100 h-5" />
        </div>
      </div>

      {item.ticketId && (
        <span className="px-2 py-0.5 rounded text-[10px] uppercase font-medium bg-[#00f2ff]/20 text-[#818cf8] border border-[#00f2ff]/30 shrink-0">
          {item.ticketId}
        </span>
      )}
    </div>
  );
}
