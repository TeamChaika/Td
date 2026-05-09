'use client';

/**
 * Страница ожидания: /reservations/{id}
 * Показывает «Готовим платёж...» и через 1 секунду перенаправляет на /pay/{id}.
 */
import { useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';

export default function ReservationPendingPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();

  useEffect(() => {
    const timer = setTimeout(() => {
      router.replace(`/pay/${params.id}`);
    }, 1000);

    return () => clearTimeout(timer);
  }, [router, params.id]);

  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-4 px-4">
      <div className="h-10 w-10 animate-spin rounded-full border-4 border-muted border-t-primary" />
      <p className="text-center text-muted-foreground">Готовим платёж...</p>
    </div>
  );
}
