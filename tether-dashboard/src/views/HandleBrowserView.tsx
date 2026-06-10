import { useState, useEffect } from 'react';
import { Download, FileDigit, Search } from 'lucide-react';
import { api } from '../api/client';
import { BlobHandleData, HandleLookupResult, HandleSummary, TreeHandleData } from '../types/handle';
import { LoadingSpinner } from '../components/shared/LoadingSpinner';
import { CopyButton } from '../components/shared/CopyButton';
import { timeAgo, truncateHandle } from '../utils/formatters';

export function HandleBrowserView() {
  const [query, setQuery] = useState('');
  const [result, setResult] = useState<HandleLookupResult | null>(null);
  const [handles, setHandles] = useState<HandleSummary[]>([]);
  const [totalHandles, setTotalHandles] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [notFound, setNotFound] = useState(false);
  const pageSize = 25;

  useEffect(() => {
    let cancelled = false;
    api.getHandles(pageSize, offset)
      .then((data) => {
        if (cancelled) return;
        setHandles(data.items);
        setTotalHandles(data.total);
      })
      .catch(console.error);
    return () => {
      cancelled = true;
    };
  }, [offset]);

  useEffect(() => {
    const timer = setTimeout(async () => {
      if (query.length < 5) {
        setResult(null);
        setNotFound(false);
        return;
      }
      
      setLoading(true);
      setNotFound(false);
      try {
        const data = await api.getHandle(query);
        setResult(data);
      } catch {
        setResult(null);
        setNotFound(true);
      } finally {
        setLoading(false);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [query]);

  return (
    <div className="max-w-5xl mx-auto p-6 flex flex-col gap-8 w-full h-full overflow-y-auto">
      <div>
        <h1 className="text-2xl font-semibold mb-2">Handle Browser</h1>
        <p className="text-[#8892b0] text-sm mb-6">Browse handles from the local Tether database.</p>
        
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-[#8892b0]" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="h&l_messages_..."
            className="w-full bg-[#0f111a] border border-[#ffffff14] focus:border-[#00f2ff] rounded-xl pl-10 pr-4 py-3 font-mono text-sm outline-none transition-colors placeholder:text-[#8892b0]"
            autoFocus
          />
          {loading && (
            <div className="absolute right-3 top-1/2 -translate-y-1/2">
              <LoadingSpinner className="w-5 h-5 text-[#00f2ff]" />
            </div>
          )}
        </div>
      </div>

      <div className="flex-1 w-full">
        {result ? (
          <HandleResultCard
            result={result}
            onSelectHandle={(handle) => {
              setQuery(handle);
              setResult(null);
              setNotFound(false);
            }}
          />
        ) : notFound ? (
          <div className="bg-[#0f111a] border border-[#ef4444]/30 rounded-xl p-5 text-center shadow-xl">
            <p className="text-[#ef4444] text-sm">Handle not found</p>
          </div>
        ) : (
          <HandleList
            handles={handles}
            total={totalHandles}
            offset={offset}
            pageSize={pageSize}
            onPage={setOffset}
            onSelect={(handle) => {
              setQuery(handle);
              setResult(null);
              setNotFound(false);
            }}
          />
        )}
      </div>
    </div>
  );
}

interface HandleListProps {
  handles: HandleSummary[];
  total: number;
  offset: number;
  pageSize: number;
  onPage: (offset: number) => void;
  onSelect: (handle: string) => void;
}

function HandleList({ handles, total, offset, pageSize, onPage, onSelect }: HandleListProps) {
  if (handles.length === 0) {
    return (
      <div className="h-40 flex items-center justify-center border border-[#ffffff14] border-dashed rounded-xl text-[#8892b0] text-sm">
        No handles found in the database.
      </div>
    );
  }

  const nextOffset = offset + pageSize;
  const prevOffset = Math.max(0, offset - pageSize);

  return (
    <div className="bg-[#0f111a] border border-[#ffffff14] rounded-2xl overflow-hidden shadow-xl">
      <div className="flex items-center justify-between gap-4 p-4 border-b border-[#ffffff14]">
        <div>
          <h2 className="text-sm font-semibold text-[#e0e6ed]">All Handles</h2>
          <p className="text-xs text-[#8892b0] mt-1">{total.toLocaleString()} total handles</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => onPage(prevOffset)}
            disabled={offset === 0}
            className="px-3 py-1.5 rounded-lg border border-[#ffffff14] text-xs text-[#e0e6ed] disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Previous
          </button>
          <button
            type="button"
            onClick={() => onPage(nextOffset)}
            disabled={nextOffset >= total}
            className="px-3 py-1.5 rounded-lg border border-[#ffffff14] text-xs text-[#e0e6ed] disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Next
          </button>
        </div>
      </div>

      <div className="divide-y divide-[#ffffff14]">
        {handles.map((item) => (
          <button
            type="button"
            key={item.handle}
            onClick={() => onSelect(item.handle)}
            className="w-full grid grid-cols-[120px_1fr_110px] md:grid-cols-[130px_1fr_110px_140px] gap-4 items-center px-4 py-3 text-left hover:bg-[#ffffff14]/5 transition-colors"
          >
            <div>
              <div className="text-xs uppercase tracking-[1px] text-[#8892b0]">{item.table}</div>
              <div className="text-[11px] text-[#8892b0]/70 mt-0.5">{item.kind}</div>
            </div>
            <div className="min-w-0">
              <div className="font-mono text-sm text-[#7000ff] truncate">{truncateHandle(item.handle)}</div>
              <div className="text-xs text-[#8892b0] truncate mt-1">
                {item.fromAgent && item.toAgent ? `${item.fromAgent} -> ${item.toAgent}` : item.subject || item.status || 'metadata'}
              </div>
            </div>
            <div className="text-xs text-[#8892b0]">{timeAgo(item.createdAt)}</div>
            <div className="hidden md:flex justify-end">
              <CopyButton text={item.handle} />
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

interface HandleResultCardProps {
  result: HandleLookupResult;
  onSelectHandle: (handle: string) => void;
}

function HandleResultCard({ result, onSelectHandle }: HandleResultCardProps) {
  return (
    <div className="bg-[#0f111a] border border-[#ffffff14] rounded-2xl overflow-hidden shadow-xl">
      <div className="flex items-center justify-between gap-4 p-4 border-b border-[#ffffff14]">
        <div className="font-mono text-sm text-[#7000ff] truncate">{result.handle}</div>
        <CopyButton text={result.handle} />
      </div>
      <div className="p-5">
        {result.kind === 'blob' && <BlobHandlePanel result={result} />}
        {result.kind === 'tree' && <TreeHandlePanel result={result} onSelectHandle={onSelectHandle} />}
        {result.kind === 'inline' && <InlineHandlePanel value={result.value} />}
        {result.kind === 'message' && <MessageHandlePanel result={result} />}
      </div>
    </div>
  );
}

function BlobHandlePanel({ result }: { result: BlobHandleData }) {
  const handleDownload = () => {
    const blob = new Blob([decodeBase64(result.bytesB64)], { type: result.contentType });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = result.handle;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-4 text-sm">
      <div className="flex items-center gap-3">
        <span className="px-2 py-1 rounded bg-[#ffffff14] border border-[#ffffff14] text-xs text-[#e0e6ed]">
          {result.contentType}
        </span>
        <span className="text-[#8892b0]">Binary blob — {result.sizeBytes} bytes</span>
      </div>
      <button
        onClick={handleDownload}
        className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-[#00f2ff] hover:bg-[#00d1d1] text-white text-sm transition-colors"
      >
        <Download className="w-4 h-4" />
        Download
      </button>
    </div>
  );
}

function TreeHandlePanel(
  { result, onSelectHandle }: { result: TreeHandleData; onSelectHandle: (handle: string) => void }
) {
  return (
    <div className="space-y-4">
      <div className="text-sm text-[#8892b0]">
        Tree handle with {result.handles.length} child{result.handles.length === 1 ? '' : 'ren'}.
      </div>
      <div className="space-y-2">
        {result.handles.map((handle) => (
          <button
            key={handle}
            onClick={() => onSelectHandle(handle)}
            className="w-full flex items-center gap-3 rounded-lg border border-[#ffffff14] bg-[#05060a] px-3 py-3 text-left hover:border-[#00f2ff]/40 transition-colors"
          >
            <FileDigit className="w-4 h-4 text-[#00f2ff] shrink-0" />
            <span className="font-mono text-sm text-[#e0e6ed] truncate">{handle}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

function InlineHandlePanel({ value }: { value: unknown }) {
  return (
    <pre className="text-sm text-[#e0e6ed] whitespace-pre-wrap break-words bg-[#05060a] border border-[#ffffff14] rounded-xl p-4 overflow-x-auto">
      {typeof value === 'string' ? value : JSON.stringify(value, null, 2)}
    </pre>
  );
}

function MessageHandlePanel({ result }: { result: Extract<HandleLookupResult, { kind: 'message' }> }) {
  return (
    <div className="space-y-4 text-sm">
      <div className="grid grid-cols-[80px_1fr] gap-2 items-center">
        <span className="text-[#8892b0]">Table:</span>
        <span className="text-[#e0e6ed]">{result.table}</span>
      </div>
      <div className="grid grid-cols-[80px_1fr] gap-2 items-center">
        <span className="text-[#8892b0]">From:</span>
        <span className="text-[#e0e6ed] truncate">{result.fromAgent}</span>
      </div>
      <div className="grid grid-cols-[80px_1fr] gap-2 items-center">
        <span className="text-[#8892b0]">To:</span>
        <span className="text-[#e0e6ed] truncate">{result.toAgent}</span>
      </div>
      <div className="grid grid-cols-[80px_1fr] gap-2 items-center">
        <span className="text-[#8892b0]">Created:</span>
        <span className="text-[#e0e6ed]">{new Date(result.createdAt).toLocaleString()}</span>
      </div>
      <div className="grid grid-cols-[80px_1fr] gap-2 items-center">
        <span className="text-[#8892b0]">Status:</span>
        <span className="text-[#e0e6ed] capitalize">{result.status}</span>
      </div>
      {result.ticketId && (
        <div className="grid grid-cols-[80px_1fr] gap-2 items-center">
          <span className="text-[#8892b0]">Ticket:</span>
          <span className="text-[#e0e6ed]">{result.ticketId}</span>
        </div>
      )}
      {result.tags.length > 0 && (
        <div className="grid grid-cols-[80px_1fr] gap-2 items-start">
          <span className="text-[#8892b0] mt-0.5">Tags:</span>
          <div className="flex flex-wrap gap-2">
            {result.tags.map((tag) => (
              <span key={tag} className="px-2 py-0.5 rounded text-xs bg-[#ffffff14] text-[#8892b0]">
                {tag}
              </span>
            ))}
          </div>
        </div>
      )}
      {result.text && (
        <pre className="text-sm text-[#e0e6ed] whitespace-pre-wrap break-words bg-[#05060a] border border-[#ffffff14] rounded-xl p-4 overflow-x-auto">
          {result.text}
        </pre>
      )}
    </div>
  );
}

function decodeBase64(value: string): Uint8Array {
  const binary = window.atob(value);
  return Uint8Array.from(binary, (char) => char.charCodeAt(0));
}
