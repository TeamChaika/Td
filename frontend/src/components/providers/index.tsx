'use client';

/**
 * Композиция всех провайдеров клиентской части.
 */
import { type ReactNode } from 'react';

import { QueryProvider } from './query-provider';
import { SessionProvider } from '@/lib/auth/session-provider';
import { ToastProvider } from '@/components/ui/toast';

export function Providers({ children }: { children: ReactNode }) {
  return (
    <QueryProvider>
      <ToastProvider>
        <SessionProvider>{children}</SessionProvider>
      </ToastProvider>
    </QueryProvider>
  );
}