'use client';

/**
 * useSession — хук для получения текущей сессии.
 * Возвращает {user, organization, loading}.
 */
import { useSessionContext } from './session-provider';

export function useSession() {
  const ctx = useSessionContext();
  return {
    user: ctx.user,
    organization: ctx.organization,
    isAuthenticated: ctx.isAuthenticated,
    loading: ctx.isLoading,
    refetch: ctx.refetch,
  };
}