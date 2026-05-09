'use client';

/**
 * Magic-link верификация. Берёт token из URL, вызывает verify.
 */
import { Suspense } from 'react';

import { MagicLinkVerify } from '@/features/auth/magic-link-page';

export default function MagicLinkPage() {
  return (
    <Suspense fallback={
      <main className="flex min-h-screen items-center justify-center">
        <p className="text-muted-foreground">Загрузка...</p>
      </main>
    }>
      <MagicLinkVerify />
    </Suspense>
  );
}