import { Loader2 } from 'lucide-react';
import { cn } from '../../utils/cn';

export function LoadingSpinner({ className }: { className?: string }) {
  return <Loader2 className={cn("w-5 h-5 animate-spin text-[#00f2ff]", className)} />;
}
