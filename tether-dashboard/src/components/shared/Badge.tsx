import { cn } from '../../utils/cn';

interface BadgeProps {
  status: 'online' | 'offline' | 'idle' | 'success' | 'warning' | 'error';
  pulse?: boolean;
}

export function Badge({ status, pulse }: BadgeProps) {
  // Use immersive theme glow colors mapping
  const isGreen = status === 'online' || status === 'success';
  const isRed = status === 'offline' || status === 'error';
  const isAmber = status === 'idle' || status === 'warning';

  return (
    <div className="relative flex items-center justify-center w-3 h-3">
      <div
        className={cn(
          "absolute w-full h-full rounded-full opacity-70",
          isGreen && "bg-[#00f2ff]",
          isRed && "bg-[#ef4444]",
          isAmber && "bg-[#f59e0b]",
          pulse && "animate-ping"
        )}
      />
      <div
        className={cn(
          "relative w-2 h-2 rounded-full",
          isGreen && "bg-[#00f2ff] shadow-[0_0_8px_#00f2ff]",
          isRed && "bg-[#ef4444] shadow-[0_0_8px_#ef4444]",
          isAmber && "bg-[#f59e0b] shadow-[0_0_8px_#f59e0b]"
        )}
      />
    </div>
  );
}
