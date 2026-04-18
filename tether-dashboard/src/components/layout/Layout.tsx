import { Outlet, Navigate } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { useAuthStore } from '../../store/authStore';
import { useEffect } from 'react';
import { connectWebSocket, disconnectWebSocket } from '../../ws/socket';

export function Layout() {
  const token = useAuthStore((s) => s.token);
  const hasInitialized = useAuthStore((s) => s.hasInitialized);

  useEffect(() => {
    if (token) {
      connectWebSocket();
    }
    return () => disconnectWebSocket();
  }, [token]);

  if (!hasInitialized) {
    return null;
  }

  if (!token) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#05060a] text-[#e0e6ed]">
      <Sidebar />
      <div className="flex flex-col flex-1 min-w-0 bg-[radial-gradient(circle_at_50%_-20%,_#151a2e_0%,_#05060a_70%)] relative">
        <TopBar />
        <main className="flex-1 overflow-auto relative z-10">
          <Outlet />
        </main>
        
        {/* Immersive UI Atmosphere Element */}
        <div className="absolute w-[300px] h-[300px] bg-[#7000ff] blur-[120px] opacity-10 bottom-[-50px] right-[-50px] pointer-events-none rounded-full z-0"></div>
      </div>
    </div>
  );
}
