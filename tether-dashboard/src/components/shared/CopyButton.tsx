import React, { useState } from 'react';
import { Copy, Check } from 'lucide-react';
import { cn } from '../../utils/cn';

interface CopyButtonProps {
  text: string;
  className?: string;
  iconOnly?: boolean;
}

export function CopyButton({ text, className, iconOnly }: CopyButtonProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy', err);
    }
  };

  return (
    <button
      onClick={handleCopy}
      className={cn(
        "flex items-center gap-1.5 px-2 py-1 text-xs font-medium rounded-md transition-colors",
        "text-[#8892b0] hover:text-[#e0e6ed] hover:bg-[#ffffff14]",
        copied && "text-[#22c55e] hover:text-[#22c55e]",
        className
      )}
      title="Copy to clipboard"
    >
      {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
      {!iconOnly && <span>{copied ? 'Copied' : 'Copy'}</span>}
    </button>
  );
}
