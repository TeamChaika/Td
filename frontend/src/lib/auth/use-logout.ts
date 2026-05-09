'use client';

/**
 * useLogout — мутация для выхода.
 * Вызывает POST /api/v1/auth/logout и очищает сессию.
 *
 * @param redirectTo — путь для редиректа после выхода (по умолчанию /admin/login).
 *   Для платформы передавать '/platform/login'.
 */
import { useMutation } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';

import { api } from '@/lib/api/client';
import { clearSession } from '@/lib/auth/session-store';

export function useLogout(redirectTo = '/admin/login') {
  const router = useRouter();

  return useMutation({
    mutationFn: async () => {
      try {
        await api('/api/v1/auth/logout', { method: 'POST' });
      } finally {
        clearSession();
      }
    },
    onSuccess: () => {
      router.push(redirectTo);
    },
    onError: () => {
      // Даже при ошибке — чистим сессию и редиректим
      clearSession();
      router.push(redirectTo);
    },
  });
}