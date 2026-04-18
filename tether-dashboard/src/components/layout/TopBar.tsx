import { useAuthStore } from '../../store/authStore';
import { useConnectionStore } from '../../store/connectionStore';
import { UI_STRINGS } from '../../utils/constants';
import { Badge } from '../shared/Badge';
import { LoadingSpinner } from '../shared/LoadingSpinner';
import { LogOut } from 'lucide-react';
import { disconnectWebSocket } from '../../ws/socket';

export function TopBar() {
  const { logout, isLocalMode } = useAuthStore();
  const { isConnected } = useConnectionStore();

  const handleLogout = () => {
    disconnectWebSocket();
    logout();
  };

  return (
    <div className="h-[80px] w-full border-b border-[#ffffff14] bg-[#05060a] flex items-center justify-between px-6 shrink-0 relative z-10">
      <div className="flex items-center gap-4">
        {/* Render TetherLite flag if applicable */}
        <div className="md:hidden flex items-center justify-center border-r pr-6 border-[#ffffff14] h-full shrink-0">
          <div className="w-[18px] h-[18px] border-[3px] border-[#00f2ff] rounded-full shadow-[0_0_10px_#00f2ff] shrink-0" />
        </div>

        <div className="flex items-center gap-2 text-sm font-medium border-r border-[#ffffff14] pr-4 h-full shrink-0">
          <div className="px-2 py-1 rounded-full bg-[#ffffff14] text-[#8892b0] flex items-center border border-[#ffffff14] text-xs font-semibold mr-1">
             {isLocalMode ? "TetherLite" : "Tether Relay"}
          </div>
          <Badge status={isLocalMode || isConnected ? 'success' : 'error'} pulse={!isLocalMode && isConnected} />
          <span className={isLocalMode || isConnected ? "text-[#00f2ff]" : "text-[#ef4444]"}>
            {isLocalMode ? 'Local Mode' : isConnected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
        {!isLocalMode && !isConnected && (
          <div className="flex items-center gap-2 px-3 py-1 bg-[#ef4444]/10 border border-[#ef4444]/20 rounded-full text-xs text-[#ef4444]">
            <LoadingSpinner className="w-3 h-3 text-[#ef4444]" />
            {UI_STRINGS.DISCONNECTED_BANNER}
          </div>
        )}
      </div>

      <div className="flex items-center gap-4">
        <div className="hidden sm:flex items-center bg-[#0f111a] border border-[#ffffff14] rounded-full px-4 py-2 text-[13px] text-[#8892b0]">
          <span className="w-2 h-2 rounded-full bg-[#00f2ff] mr-2 shadow-[0_0_8px_#00f2ff]"></span>
          Indie Tier
        </div>
        {!isLocalMode && (
          <button 
            onClick={handleLogout}
            className="text-[#8892b0] hover:text-[#e0e6ed] transition-colors p-2"
            title="Disconnect session"
          >
            <LogOut className="w-4 h-4" />
          </button>
        )}
      </div>
    </div>
  );
}
