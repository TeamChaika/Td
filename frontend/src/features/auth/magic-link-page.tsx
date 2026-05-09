'use client';

/**
 * Magic-link верификация. Берёт token из URL, вызывает verify.
 */
import { useEffect, useRef, useState } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import Link from 'next/link';

import { Button } from '@/components/ui/button';
import { Spinner } from '@/components/ui/spinner';
import { useMagicLinkVerify } from '@/lib/auth/use-magic-link';
import { isApiError } from '@/lib/api/errors';

export function MagicLinkVerify() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const verify = useMagicLinkVerify();
  const [error, setError] = useState<string | null>(null);
  const called = useRef(false);

  useEffect(() => {
    if (called.current) return;
    called.current = true;

    const token = searchParams.get('token');
    if (!token) {
      setError('Не указан токен для входа.');
      return;
    }

    verify.mutateAsync({ token })
      .then((session) => {
        if (session.user?.role === 'superadmin') {
          router.push('/platform');
        } else {
          router.push('/admin');
        }
      })
      .catch((err) => {
        if (isApiError(err)) {
          setError(err.message);
        } else {
          setError('Не удалось подтвердить вход. Попробуйте запросить новую ссылку.');
        }
      });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <main className="flex min-h-screen items-center justify-center px-6">
      <div className="w-full max-w-md text-center">
        {!error ? (
          <div className="space-y-4">
            <Spinner size="lg" className="mx-auto" />
            <p className="text-lg text-muted-foreground">Выполняем вход...</p>
          </div>
        ) : (
          <div className="rounded-lg border border-red-600/30 bg-red-600/10 p-6 space-y-4">
            <h1 className="text-xl font-semibold text-red-400">Ошибка входа</h1>
            <p className="text-sm text-muted-foreground">{error}</p>
            <Button asChild>
              <Link href="/admin/login">← Вернуться ко входу</Link>
            </Button>
          </div>
        )}
      </div>
    </main>
  );
}