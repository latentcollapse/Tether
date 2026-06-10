import { NavLink } from 'react-router-dom';
import { Network, Search, Activity, Mail, Link as LinkIcon, Settings, ClipboardList, History } from 'lucide-react';
import { cn } from '../../utils/cn';
import { useInboxStore } from '../../store/inboxStore';

export function Sidebar() {
  const { unreadCount } = useInboxStore();

  const navItems = [
    { to: "/", icon: Network, label: "Network" },
    { to: "/messages", icon: Mail, label: "Messages", badge: unreadCount },
    { to: "/connection", icon: LinkIcon, label: "Connection" },
    { to: "/board", icon: ClipboardList, label: "Job Board" },
    { to: "/changelog", icon: History, label: "Changelog" },
    { to: "/usage", icon: Activity, label: "Usage" },
    { to: "/settings", icon: Settings, label: "Settings" },
  ];

  return (
    <div className="w-16 md:w-60 h-full border-r border-[#ffffff14] bg-[#05060a] flex flex-col items-center md:items-start shrink-0 transition-all">
      <div className="h-[80px] flex items-center md:px-6 justify-center w-full md:justify-start border-b border-[#ffffff14] shrink-0">
        <div className="w-[18px] h-[18px] border-[3px] border-[#00f2ff] rounded-full shadow-[0_0_10px_#00f2ff] shrink-0" />
        <span className="ml-2.5 font-[800] text-[#00f2ff] text-[20px] tracking-[-1px] uppercase hidden md:block">Tether</span>
      </div>

      <nav className="flex-1 w-full py-4 flex flex-col gap-1 px-2 md:px-3">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) => cn(
              "flex items-center justify-between w-full px-2 md:px-3 py-2 rounded-lg transition-colors group relative",
              isActive 
                ? "bg-[rgba(255,255,255,0.03)] text-[#00f2ff] border-l-[3px] border-[#00f2ff] rounded-l-none" 
                : "text-[#8892b0] hover:bg-[rgba(255,255,255,0.03)] hover:text-[#e0e6ed]"
            )}
          >
            <div className="flex items-center">
              <item.icon className="w-5 h-5 shrink-0" />
              <span className="ml-3 font-medium hidden md:block">{item.label}</span>
            </div>
            {item.badge ? (
              <div className="hidden md:flex items-center justify-center bg-[#00f2ff] text-[#05060a] text-[10px] font-bold h-5 min-w-5 px-1.5 rounded-full">
                {item.badge}
              </div>
            ) : null}
            {item.badge && (
              <div className="md:hidden absolute top-2 right-2 w-2 h-2 bg-[#00f2ff] rounded-full shadow-[0_0_4px_#00f2ff]" />
            )}
          </NavLink>
        ))}
      </nav>
      
      <div className="p-4 border-t border-[#ffffff14] w-full hidden md:block text-xs text-[#8892b0]">
        Tether v0.1.0-alpha
      </div>
    </div>
  );
}
