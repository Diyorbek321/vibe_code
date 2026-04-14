/**
 * <<< INTEGRATION: real JWT-based auth store >>>
 *
 * Changes from original:
 *   1. loginWithApi(email, password) — one API call, no GET /me
 *      JWT payload now carries email + full_name so we decode it client-side
 *   2. Token persisted in localStorage; rehydrated on page reload
 *   3. logout() clears token
 *   4. finance:unauthorized event → auto-logout on any 401
 *
 * Existing interface preserved:
 *   login(user), logout(), completeOnboarding() — signatures unchanged
 */

import { create } from 'zustand';
import { User } from '../types';
import { http, tokenStorage } from '../lib/api';

// ── JWT client-side decode (no verification — just reading claims) ──────────
interface JwtClaims {
  sub: string;
  company_id: string;
  email?: string;
  full_name?: string;
  exp: number;
}

function decodeJwt(token: string): JwtClaims | null {
  try {
    const part = token.split('.')[1];
    const json = atob(part.replace(/-/g, '+').replace(/_/g, '/'));
    return JSON.parse(json) as JwtClaims;
  } catch {
    return null;
  }
}

function isExpired(claims: JwtClaims): boolean {
  return Date.now() / 1000 > claims.exp;
}

// ── Session rehydration from localStorage ──────────────────────────────────
// Called once at module load — no network call needed
function tryRehydrate(): { user: User | null; token: string | null; isAuthenticated: boolean } {
  const token = tokenStorage.get();
  if (!token) return { user: null, token: null, isAuthenticated: false };

  const claims = decodeJwt(token);
  if (!claims || isExpired(claims)) {
    tokenStorage.clear();
    return { user: null, token: null, isAuthenticated: false };
  }

  return {
    token,
    isAuthenticated: true,
    user: {
      id: claims.sub,
      email: claims.email ?? '',
      name: claims.full_name ?? '',
      isOnboarded: true,
    },
  };
}

const rehydrated = tryRehydrate();

// ── Store ──────────────────────────────────────────────────────────────────

interface ApiTokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  login: (user: User) => void;
  logout: () => void;
  completeOnboarding: () => void;
  loginWithApi: (email: string, password: string) => Promise<void>;
  registerWithApi: (
    email: string,
    password: string,
    fullName: string,
    companyName: string,
  ) => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  ...rehydrated,

  login: (user: User) => set({ user, isAuthenticated: true }),

  logout: () => {
    tokenStorage.clear();
    set({ user: null, token: null, isAuthenticated: false });
  },

  completeOnboarding: () =>
    set((state) => ({
      user: state.user ? { ...state.user, isOnboarded: true } : null,
    })),

  // Single network call — profile decoded from the JWT payload
  loginWithApi: async (email: string, password: string) => {
    const res = await http.post<ApiTokenResponse>('/api/auth/login', { email, password });

    tokenStorage.set(res.access_token);

    const claims = decodeJwt(res.access_token);
    const user: User = {
      id: claims?.sub ?? '',
      email: claims?.email ?? email,
      name: claims?.full_name ?? '',
      isOnboarded: true,
    };

    set({ token: res.access_token, user, isAuthenticated: true });
  },

  // Register: creates company + user, then logs in automatically
  registerWithApi: async (
    email: string,
    password: string,
    fullName: string,
    companyName: string,
  ) => {
    await http.post('/api/auth/register', {
      email,
      password,
      full_name: fullName,
      company_name: companyName,
    });

    // Auto-login after successful registration
    const res = await http.post<ApiTokenResponse>('/api/auth/login', { email, password });

    tokenStorage.set(res.access_token);

    const claims = decodeJwt(res.access_token);
    const user: User = {
      id: claims?.sub ?? '',
      email: claims?.email ?? email,
      name: claims?.full_name ?? fullName,
      isOnboarded: true,
    };

    set({ token: res.access_token, user, isAuthenticated: true });
  },
}));

// Auto-logout on any 401 response (dispatched by api.ts)
window.addEventListener('finance:unauthorized', () => {
  tokenStorage.clear();
  useAuthStore.setState({ user: null, token: null, isAuthenticated: false });
});
