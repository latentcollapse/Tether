import { HandleMetadata } from '../../types/handle';
import { CopyButton } from '../shared/CopyButton';
import { Badge } from '../shared/Badge';
import { UI_STRINGS } from '../../utils/constants';

interface HandleCardProps {
  handleHash: string;
  metadata?: HandleMetadata | null;
}

export function HandleCard({ handleHash, metadata }: HandleCardProps) {
  if (!metadata) {
    return (
      <div className="bg-[#0f111a] border border-[#ef4444]/30 rounded-xl p-5 text-center shadow-xl">
        <p className="text-[#ef4444] text-sm">{UI_STRINGS.HANDLE_NOT_FOUND}</p>
      </div>
    );
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'open': return 'success';
      case 'stale': return 'warning';
      case 'closed': case 'read': default: return 'error';
    }
  };

  return (
    <div className="bg-[#0f111a] border border-[#ffffff14] rounded-2xl overflow-hidden shadow-xl stat-card-gradient relative">
      <div className="flex items-center justify-between p-4 border-b border-[#ffffff14] bg-[#0f111a]">
        <div className="font-mono text-sm text-[#7000ff] truncate mr-4">
          {handleHash}
        </div>
        <CopyButton text={handleHash} />
      </div>
      
      <div className="p-5 space-y-4 text-sm">
        <div className="grid grid-cols-[80px_1fr] gap-2 items-center">
          <span className="text-[#8892b0]">Table:</span>
          <span className="text-[#e0e6ed]">{metadata.table}</span>
        </div>
        <div className="grid grid-cols-[80px_1fr] gap-2 items-center">
          <span className="text-[#8892b0]">From:</span>
          <span className="text-[#e0e6ed] truncate">{metadata.fromAgent}</span>
        </div>
        <div className="grid grid-cols-[80px_1fr] gap-2 items-center">
          <span className="text-[#8892b0]">To:</span>
          <span className="text-[#e0e6ed] truncate">{metadata.toAgent}</span>
        </div>
        <div className="grid grid-cols-[80px_1fr] gap-2 items-center">
          <span className="text-[#8892b0]">Created:</span>
          <span className="text-[#e0e6ed]">{new Date(metadata.createdAt).toLocaleString()}</span>
        </div>
        <div className="grid grid-cols-[80px_1fr] gap-2 items-center">
          <span className="text-[#8892b0]">Status:</span>
          <div className="flex items-center gap-2">
            <span className="text-[#e0e6ed] capitalize">{metadata.status}</span>
            <Badge status={getStatusColor(metadata.status)} pulse={metadata.status === 'open'} />
          </div>
        </div>
        
        {metadata.ticketId && (
          <div className="grid grid-cols-[80px_1fr] gap-2 items-center">
            <span className="text-[#8892b0]">Ticket:</span>
            <span className="text-[#e0e6ed]">{metadata.ticketId}</span>
          </div>
        )}

        {metadata.tags && metadata.tags.length > 0 && (
          <div className="grid grid-cols-[80px_1fr] gap-2 items-start mt-2 pt-4 border-t border-[#ffffff14]/50">
            <span className="text-[#8892b0] mt-0.5">Tags:</span>
            <div className="flex flex-wrap gap-2">
              {metadata.tags.map(tag => (
                <span key={tag} className="px-2 py-0.5 rounded text-xs bg-[#ffffff14] text-[#8892b0]">
                  {tag}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
