import React from 'react';
import { UI_STRINGS } from '../../utils/constants';
import { IssuedKey } from '../../types/tier';
import { Badge } from '../shared/Badge';
import { CopyButton } from '../shared/CopyButton';
import { timeAgo } from '../../utils/formatters';

interface KeyCardProps {
  apiKey: IssuedKey;
  onRevoke: (id: string) => void;
  onRotate: (id: string) => void;
}

export const KeyCard: React.FC<KeyCardProps> = ({ apiKey, onRevoke, onRotate }) => {
  const usagePercent = Math.min(100, Math.round((apiKey.usage.messagesUsedToday / apiKey.usage.messageLimitToday) * 100));
  
  const usageColor = usagePercent > 95 ? 'bg-[#ef4444]' : usagePercent > 80 ? 'bg-[#f59e0b]' : 'bg-[#00f2ff]';

  return (
    <div className="bg-[#0f111a] border border-[#ffffff14] rounded-2xl flex flex-col overflow-hidden stat-card-gradient relative">
      <div className="p-4 border-b border-[#ffffff14] flex items-center justify-between">
        <div className="font-medium flex items-center gap-2">
          {apiKey.agentName}
        </div>
        <div className="flex items-center gap-2 text-xs font-medium text-[#8892b0] bg-[#ffffff14]/50 px-2 py-1 rounded">
          {apiKey.isActive ? 'Active' : 'Revoked'}
          <Badge status={apiKey.isActive ? 'online' : 'error'} />
        </div>
      </div>

      <div className="p-4 space-y-4 text-sm flex-1">
        <div className="grid grid-cols-[80px_1fr] gap-2 items-center">
          <span className="text-[#8892b0]">Key:</span>
          <div className="flex items-center justify-between font-mono text-[#e0e6ed] bg-[#05060a] px-2 py-1.5 rounded border border-[#ffffff14]">
            <span>{apiKey.maskedKey}</span>
            {/* Can't actually copy masked text, but UI simulates the feature */}
            <CopyButton text={apiKey.maskedKey} iconOnly />
          </div>
        </div>
        
        <div className="grid grid-cols-[80px_1fr] gap-2 items-center text-[#8892b0]">
          <span className="text-[#8892b0]">Tier:</span>
          <span>{apiKey.tier}</span>
        </div>
        
        <div className="grid grid-cols-[80px_1fr] gap-2 items-center text-[#8892b0]">
          <span className="text-[#8892b0]">Issued:</span>
          <span>{new Date(apiKey.issuedAt).toLocaleDateString()}</span>
        </div>
        
        <div className="grid grid-cols-[80px_1fr] gap-2 items-center text-[#8892b0]">
          <span className="text-[#8892b0]">Last used:</span>
          <span>{timeAgo(apiKey.lastUsedAt)}</span>
        </div>
        
        <div className="mt-4 pt-4 border-t border-[#ffffff14]">
          <div className="flex justify-between items-center mb-1.5 text-xs text-[#8892b0]">
            <span>Usage: {apiKey.usage.messagesUsedToday.toLocaleString()} / {apiKey.usage.messageLimitToday.toLocaleString()} today</span>
            <span>{usagePercent}%</span>
          </div>
          <div className="w-full h-2 bg-[#ffffff14] rounded-full overflow-hidden">
            <div className={`h-full ${usageColor} transition-all`} style={{ width: `${usagePercent}%` }} />
          </div>
        </div>
      </div>
      
      <div className="p-3 border-t border-[#ffffff14] flex items-center justify-end gap-2 bg-[#0f111a]">
        <button 
          onClick={() => onRotate(apiKey.id)}
          disabled={!apiKey.isActive}
          className="px-3 py-1.5 text-xs font-medium text-[#e0e6ed] bg-[#ffffff14] hover:bg-[#8892b0] rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Rotate Key
        </button>
        <button 
          onClick={() => {
            if (window.confirm(UI_STRINGS.REVOKE_CONFIRM_BODY)) {
              onRevoke(apiKey.id);
            }
          }}
          disabled={!apiKey.isActive}
          className="px-3 py-1.5 text-xs font-medium text-white bg-[#ef4444]/90 hover:bg-[#ef4444] rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Revoke
        </button>
      </div>
    </div>
  );
}
