'use client';

/**
 * SessionProvider — React Context для данных сессии.
 *
 * При монтировании всегда вызывает GET /api/v1/auth/me.
 * Если пользователь авторизован (есть refresh-кука) — ofetch-интерцептор
 * в client.ts сам сделает refresh при 401 и повторит запрос.
 * Если refresh не удался — сессия очищается, пользователь неавторизован.
 *
 * Для организатора дополнительно загружает GET /api/v1/organizer/organization.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from 'react';

import {
  getSessionState,
  setSessionData,
  clearSession,
  subscribe,
} from '@/lib/auth/session-store';
import { api } from '@/lib/api/client';
import type { UserProfile, OrganizationProfile } from '@/types/api';

interface SessionContextValue {
  user: UserProfile | null;
  organization: OrganizationProfile | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  refetch: () => void;
}

const SessionContext = createContext<SessionContextValue>({
  user: null,
  organization: null,
  isAuthenticated: false,
  isLoading: true,
  refetch: () => {},
});

export function useSessionContext(): SessionContextValue {
  return useContext(SessionContext);
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const sessionState = useSyncExternalStore(
    subscribe,
    getSessionState,
    getSessionState,
  );

  const [isLoading, setIsLoading] = useState(true);
  const mountedRef = useRef(false);

  const fetchSession = useCallback(async () => {
    setIsLoading(true);
    try {
      // GET /api/v1/auth/me — при 401 клиент сам сделает refresh через куку
      const user = await api<UserProfile>('/api/v1/auth/me');

      let organization: OrganizationProfile | null = null;
      // Если пользователь — организатор, загружаем данные организации
      if (user.organization_id && user.role === 'organizer') {
        try {
          organization = await api<OrganizationProfile>(
            '/api/v1/organizer/organization',
          );
        } catch {
          // Организация недоступна (например, suspended) — не фатально
          organization = null;
        }
      }

      setSessionData(user, organization);
    } catch {
      clearSession();
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Всегда вызываем fetchSession при монтировании
  useEffect(() => {
    if (!mountedRef.current) {
      mountedRef.current = true;
      fetchSession();
    }
  }, [fetchSession]);

  const refetch = useCallback(() => {
    fetchSession();
  }, [fetchSession]);

  const value = useMemo<SessionContextValue>(
    () => ({
      user: sessionState.user,
      organization: sessionState.organization,
      isAuthenticated: sessionState.isAuthenticated,
      isLoading,
      refetch,
    }),
    [sessionState, isLoading, refetch],
  );

  return (
    <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
  );
}