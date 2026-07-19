import { create } from "zustand";

export interface AuthUser {
  id: string;
  email: string;
  name?: string | null;
  tenant_id: string;
  roles: string[];
}

interface AuthState {
  /** Short-lived access token — in memory ONLY, never persisted to storage.
   *  The long-lived refresh token lives in an httpOnly cookie the browser
   *  cannot read (see /api/session/*), so an XSS cannot exfiltrate a session. */
  accessToken: string | null;
  user: AuthUser | null;
  /** True once the boot-time session restore (/api/session/refresh) has run, so
   *  guards don't redirect during the initial in-memory-token gap after reload. */
  bootstrapped: boolean;
  setAccessToken: (token: string | null) => void;
  setUser: (user: AuthUser | null) => void;
  setBootstrapped: (value: boolean) => void;
  clear: () => void;
  isAuthenticated: () => boolean;
  hasRole: (...roles: string[]) => boolean;
}

// Deliberately NOT wrapped in `persist`: tokens must never reach localStorage.
// A reload re-derives the access token from the httpOnly refresh cookie.
export const useAuthStore = create<AuthState>()((set, get) => ({
  accessToken: null,
  user: null,
  bootstrapped: false,
  setAccessToken: (token) => set({ accessToken: token }),
  setUser: (user) => set({ user }),
  setBootstrapped: (value) => set({ bootstrapped: value }),
  clear: () => set({ accessToken: null, user: null }),
  isAuthenticated: () => Boolean(get().accessToken),
  hasRole: (...roles) => {
    const userRoles = get().user?.roles ?? [];
    return roles.some((r) => userRoles.includes(r));
  },
}));
