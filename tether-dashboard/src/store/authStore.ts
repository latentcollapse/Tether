import { create } from 'zustand';

interface AuthState {
  token: string | null;
  isAdmin: boolean;
  isLocalMode: boolean;
  isValidating: boolean;
  hasInitialized: boolean;
  login: (token: string, isAdmin?: boolean, isLocalMode?: boolean) => void;
  logout: () => void;
  setValidating: (v: boolean) => void;
  setLocalMode: (v: boolean) => void;
  setInitialized: (v: boolean) => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  token: null,
  isAdmin: false,
  isLocalMode: false,
  isValidating: false,
  hasInitialized: false,
  login: (token: string, isAdmin = false, isLocalMode = false) => (
    set({ token, isAdmin, isLocalMode, isValidating: false, hasInitialized: true })
  ),
  logout: () => set({ token: null, isAdmin: false, isLocalMode: false }),
  setValidating: (v: boolean) => set({ isValidating: v }),
  setLocalMode: (v: boolean) => set({ isLocalMode: v }),
  setInitialized: (v: boolean) => set({ hasInitialized: v }),
}));
