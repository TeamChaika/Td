'use client';

/**
 * useMagicLinkRequest — запрос magic-link на email.
 * useMagicLinkVerify — верификация magic-link токена и вход.
 */
import { useMutation } from '@tanstack/react-query';

import { api } from '@/lib/api/client';
import { setAccessToken, setSessionData } from '@/lib/auth/session-store';
import type {
  MagicLinkRequest,
  MagicLinkVerifyRequest,
  TokenPair,
  SessionData,
} from '@/types/api';

export function useMagicLinkRequest() {
  return useMutation({
    mutationFn: async (data: MagicLinkRequest) => {
      return api<{ message: string }>('/api/v1/auth/magic-link/request', {
        method: 'POST',
        body: data,
      });
    },
  });
}

export function useMagicLinkVerify() {
  return useMutation({
    mutationFn: async (data: MagicLinkVerifyRequest) => {
      const tokens = await api<TokenPair>('/api/v1/auth/magic-link/verify', {
        method: 'POST',
        body: data,
      });
      setAccessToken(tokens.access_token);

      const session = await api<SessionData>('/api/v1/auth/me');
      setSessionData(session.user, session.organization);

      return session;
    },
  });
}