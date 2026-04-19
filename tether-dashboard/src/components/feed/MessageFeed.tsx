import { useEffect, useState } from 'react';
import { useMessageStore } from '../../store/messageStore';
import { FeedItem } from './FeedItem';
import { Pause, Play, Trash2 } from 'lucide-react';
import { HandleCard } from '../handles/HandleCard';
import { api } from '../../api/client';
import { HandleLookupResult } from '../../types/handle';

export function MessageFeed() {
  const { feed, isPaused, setPaused, clearFeed } = useMessageStore();
  const [selectedHandle, setSelectedHandle] = useState<string | null>(null);
  const [selectedDetail, setSelectedDetail] = useState<HandleLookupResult | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!selectedHandle) {
      setSelectedDetail(null);
      return;
    }
    api.getHandle(selectedHandle)
      .then((detail) => {
        if (!cancelled) setSelectedDetail(detail);
      })
      .catch(() => {
        if (!cancelled) setSelectedDetail(null);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedHandle]);

  return (
    <div className="flex flex-col h-full bg-[#0f111a] border-l border-[#ffffff14]">
      <div className="flex items-center justify-between px-4 h-12 border-b border-[#ffffff14] shrink-0">
        <h2 className="text-sm font-semibold text-[#e0e6ed]">Real-time Feed</h2>
        <div className="flex items-center gap-1 text-[#8892b0]">
          <button 
            onClick={() => setPaused(!isPaused)}
            className="p-1.5 hover:bg-[#ffffff14] rounded transition-colors hover:text-[#e0e6ed]"
            title={isPaused ? "Resume feed" : "Pause feed"}
          >
            {isPaused ? <Play className="w-4 h-4 text-[#ef4444]" /> : <Pause className="w-4 h-4" />}
          </button>
          <button 
            onClick={clearFeed}
            className="p-1.5 hover:bg-[#ffffff14] rounded transition-colors hover:text-[#e0e6ed]"
            title="Clear feed"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {feed.length === 0 ? (
          <div className="flex flex-col items-center justify-center p-8 text-center h-full text-[#8892b0]">
            <p className="text-sm">No routing events yet.</p>
          </div>
        ) : (
          feed.map(item => (
            <FeedItem 
              key={item.id} 
              item={item} 
              onClick={() => setSelectedHandle(item.handle)}
            />
          ))
        )}
      </div>

      {selectedHandle && (
        <div className="absolute inset-0 bg-[#05060a]/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="w-full max-w-lg relative">
            <button 
              className="absolute -top-3 -right-3 w-8 h-8 bg-[#ffffff14] hover:bg-[#8892b0] text-white rounded-full flex items-center justify-center transition-colors z-10"
              onClick={() => { setSelectedHandle(null); setSelectedDetail(null); }}
            >
              ×
            </button>
            {selectedDetail?.kind === 'message' ? (
              <HandleCard handleHash={selectedHandle} metadata={selectedDetail} />
            ) : (
              <div className="bg-[#0f111a] border border-[#ffffff14] rounded-2xl overflow-hidden shadow-xl p-5">
                <div className="font-mono text-sm text-[#7000ff] truncate mb-4">{selectedHandle}</div>
                <pre className="text-xs text-[#e0e6ed] whitespace-pre-wrap break-words bg-[#05060a] border border-[#ffffff14] rounded-xl p-4 overflow-x-auto">
                  {selectedDetail ? JSON.stringify(selectedDetail, null, 2) : 'Loading handle metadata...'}
                </pre>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
