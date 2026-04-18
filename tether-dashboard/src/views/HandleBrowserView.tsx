import { useState, useEffect } from 'react';
import { Download, FileDigit, Search } from 'lucide-react';
import { api } from '../api/client';
import { BlobHandleData, HandleLookupResult, TreeHandleData } from '../types/handle';
import { LoadingSpinner } from '../components/shared/LoadingSpinner';
import { CopyButton } from '../components/shared/CopyButton';

export function HandleBrowserView() {
  const [query, setQuery] = useState('');
  const [result, setResult] = useState<HandleLookupResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [notFound, setNotFound] = useState(false);

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
    <div className="max-w-2xl mx-auto p-6 flex flex-col gap-8 w-full h-full">
      <div>
        <h1 className="text-2xl font-semibold mb-2">Handle Browser</h1>
        <p className="text-[#8892b0] text-sm mb-6">Lookup routing metadata by handle hash. Content is not available.</p>
        
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
          <div className="h-40 flex items-center justify-center border border-[#ffffff14] border-dashed rounded-xl text-[#8892b0] text-sm">
            Enter a handle above to view routing details
          </div>
        )}
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
