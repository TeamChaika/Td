/**
 * In-memory session store.
 * Access token хранится только в памяти (не localStorage/sessionStorage).
 * Refresh token — в httpOnly cookie, невидим JS.
 *
 * Использует module-level state + subscribe для реактивности.
 */

import type { UserProfile, OrganizationProfile } from '@/types/api';

export interface SessionState {
  accessToken: string | null;
  user: UserProfile | null;
  organization: OrganizationProfile | null;
  isAuthenticated: boolean;
}

type Listener = () => void;

let state: SessionState = {
  accessToken: null,
  user: null,
  organization: null,
  isAuthenticated: false,
};

const listeners = new Set<Listener>();

function notify(): void {
  listeners.forEach((fn) => fn());
}

export function getSessionState(): SessionState {
  return state;
}

export function subscribe(listener: Listener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function setAccessToken(token: string | null): void {
  state = { ...state, accessToken: token };
  notify();
}

export function setSessionData(
  user: UserProfile | null,
  organization: OrganizationProfile | null,
): void {
  state = {
    ...state,
    user,
    organization,
    isAuthenticated: user !== null,
  };
  notify();
}

export function clearSession(): void {
  state = {
    accessToken: null,
    user: null,
    organization: null,
    isAuthenticated: false,
  };
  notify();
}

/** Получить текущий access token (для API-клиента). */
export function getAccessToken(): string | null {
  return state.accessToken;
}