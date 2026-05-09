'use client';

/**
 * useLogin — мутация для входа по email+password.
 */
import { useMutation } from '@tanstack/react-query';

import { api } from '@/lib/api/client';
import { setAccessToken, setSessionData } from '@/lib/auth/session-store';
import type { LoginRequest, TokenPair, SessionData } from '@/types/api';

export function useLogin() {
  return useMutation({
    mutationFn: async (data: LoginRequest) => {
      const tokens = await api<TokenPair>('/api/v1/auth/login', {
        method: 'POST',
        body: data,
      });
      setAccessToken(tokens.access_token);

      // Загружаем профиль
      const session = await api<SessionData>('/api/v1/auth/me');
      setSessionData(session.user, session.organization);

      return session;
    },
  });
}