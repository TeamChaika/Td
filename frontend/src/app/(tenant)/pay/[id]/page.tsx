'use client';

/**
 * Страница оплаты: /pay/{reservation_id}
 *
 * Показывает QR-код для оплаты через QRM, таймер, сумму.
 * Поллит статус платежа каждые 3 секунды.
 * При успешной оплате редиректит на страницу билетов.
 */
import { useEffect, useCallback, useRef, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';

import { getPaymentStatus, processPayment } from '@/lib/api/public-payments';
import { useTenantSlug } from '@/lib/tenant/use-tenant';
import { isApiError } from '@/lib/api/errors';
import { formatKopecks } from '@/lib/utils/money';
import { useToast } from '@/components/ui/toast';
import { Button } from '@/components/ui/button';

type Phase =
  | { stage: 'loading' }
  | { stage: 'error'; message: string }
  | { stage: 'expired' }
  | { stage: 'cancelled' }
  | {
      stage: 'payment';
      qr_url: string | null;
      qr_image_base64: string | null;
      amount_kopecks: number;
      expires_at: string;
    }
  | { stage: 'paid' };

function computeRemaining(expiresAt: string): number {
  const target = new Date(expiresAt).getTime();
  const now = Date.now();
  return Math.max(0, target - now);
}

function formatTime(ms: number): string {
  const totalSec = Math.ceil(ms / 1000);
  const min = Math.floor(totalSec / 60);
  const sec = totalSec % 60;
  return `${min}:${sec.toString().padStart(2, '0')}`;
}

export default function PayPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const reservationId = params.id;
  const tenantSlug = useTenantSlug();
  const toast = useToast();

  const [phase, setPhase] = useState<Phase>({ stage: 'loading' });
  const [remaining, setRemaining] = useState<number>(0);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startedRef = useRef(false);

  // Инициализация платежа
  const initPayment = useCallback(async () => {
    if (!tenantSlug) return;
    setPhase({ stage: 'loading' });

    try {
      // Сначала проверяем статус
      let status = await getPaymentStatus(reservationId, tenantSlug);

      if (status.status === 'paid') {
        setPhase({ stage: 'paid' });
        return;
      }

      if (status.status === 'expired') {
        setPhase({ stage: 'expired' });
        return;
      }

      if (status.status === 'cancelled') {
        setPhase({ stage: 'cancelled' });
        return;
      }

      // Если нет активного QRM-платежа — создаём
      if (!status.payment_id || !status.qr_url) {
        const result = await processPayment(reservationId, tenantSlug);
        setPhase({
          stage: 'payment',
          qr_url: result.qr_url,
          qr_image_base64: result.qr_image_base64,
          amount_kopecks: result.amount_kopecks,
          expires_at: result.expires_at,
        });
        setRemaining(computeRemaining(result.expires_at));
      } else {
        setPhase({
          stage: 'payment',
          qr_url: status.qr_url,
          qr_image_base64: status.qr_image_url,
          amount_kopecks: status.amount_kopecks,
          expires_at: status.expires_at!,
        });
        setRemaining(computeRemaining(status.expires_at!));
      }
    } catch (err) {
      const message = isApiError(err) ? err.message : 'Ошибка загрузки платежа';
      setPhase({ stage: 'error', message });
      toast.error(message);
    }
  }, [reservationId, tenantSlug, toast]);

  // Первый запуск
  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;
    void initPayment();
  }, [initPayment]);

  // Таймер обратного отсчёта
  useEffect(() => {
    if (phase.stage !== 'payment' || remaining <= 0) return;

    const timer = setInterval(() => {
      setRemaining((prev) => {
        if (prev <= 1000) return 0;
        return prev - 1000;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [phase.stage, remaining]);

  // Поллинг статуса
  useEffect(() => {
    if (phase.stage !== 'payment' || !tenantSlug) return;

    pollRef.current = setInterval(async () => {
      try {
        const status = await getPaymentStatus(reservationId, tenantSlug);
        if (status.status === 'paid') {
          setPhase({ stage: 'paid' });
        } else if (status.status === 'expired') {
          setPhase({ stage: 'expired' });
        } else if (status.status === 'cancelled') {
          setPhase({ stage: 'cancelled' });
        }
      } catch {
        // Игнорируем ошибки поллинга
      }
    }, 3000);

    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [phase.stage, reservationId, tenantSlug]);

  // Редирект после оплаты
  useEffect(() => {
    if (phase.stage === 'paid') {
      const timer = setTimeout(() => {
        router.push(`/reservations/${reservationId}`);
      }, 1500);
      return () => clearTimeout(timer);
    }
    if (phase.stage === 'expired') {
      const timer = setTimeout(() => {
        router.push('/');
      }, 5000);
      return () => clearTimeout(timer);
    }
  }, [phase.stage, reservationId, router]);

  // Рендер
  return (
    <div className="mx-auto max-w-md px-4 py-8 sm:py-16">
      {phase.stage === 'loading' && (
        <div className="flex flex-col items-center gap-4 py-16">
          <div className="h-10 w-10 animate-spin rounded-full border-4 border-muted border-t-primary" />
          <p className="text-muted-foreground">Загрузка платежа...</p>
        </div>
      )}

      {phase.stage === 'error' && (
        <div className="text-center py-16 space-y-4">
          <p className="text-destructive font-medium">{phase.message}</p>
          <Button onClick={initPayment} variant="outline">
            Попробовать снова
          </Button>
        </div>
      )}

      {phase.stage === 'expired' && (
        <div className="text-center py-16 space-y-4">
          <div className="text-4xl">⏰</div>
          <h1 className="text-xl font-bold">Время оплаты истекло</h1>
          <p className="text-muted-foreground">
            Бронирование отменено. Вы можете создать новое.
          </p>
          <Link href="/" className="text-primary hover:underline text-sm">
            Вернуться на главную
          </Link>
        </div>
      )}

      {phase.stage === 'cancelled' && (
        <div className="text-center py-16 space-y-4">
          <h1 className="text-xl font-bold">Платёж отменён</h1>
          <p className="text-muted-foreground">
            Бронирование было отменено.
          </p>
          <Link href="/" className="text-primary hover:underline text-sm">
            Вернуться на главную
          </Link>
        </div>
      )}

      {phase.stage === 'payment' && (
        <div className="space-y-6">
          {/* Таймер и сумма */}
          <div className="text-center space-y-2">
            <div
              className={`text-2xl font-mono font-bold tabular-nums ${
                remaining < 60_000 ? 'text-destructive animate-pulse' : 'text-foreground'
              }`}
            >
              {formatTime(remaining)}
            </div>
            <p className="text-3xl font-bold" style={{ color: 'var(--brand, hsl(217 91% 60%))' }}>
              {formatKopecks(phase.amount_kopecks)}
            </p>
            <p className="text-sm text-muted-foreground">
              Отсканируйте QR-код в приложении банка
            </p>
          </div>

          {/* QR-код */}
          <div className="flex justify-center">
            {phase.qr_image_base64 ? (
              <img
                src={`data:image/png;base64,${phase.qr_image_base64}`}
                alt="QR-код для оплаты"
                className="w-64 h-64 rounded-lg border border-border"
              />
            ) : phase.qr_url ? (
              <div className="w-64 h-64 rounded-lg border border-border bg-white p-4 flex items-center justify-center">
                <img
                  src={phase.qr_url}
                  alt="QR-код для оплаты"
                  className="max-w-full max-h-full"
                />
              </div>
            ) : (
              <div className="w-64 h-64 rounded-lg border border-border bg-muted flex items-center justify-center">
                <p className="text-muted-foreground text-sm">QR-код недоступен</p>
              </div>
            )}
          </div>

          {/* Инструкция */}
          <div className="text-center space-y-1 text-sm text-muted-foreground">
            <p>1. Откройте приложение банка</p>
            <p>2. Отсканируйте QR-код</p>
            <p>3. Подтвердите платёж</p>
          </div>

          <p className="text-xs text-center text-muted-foreground">
            Оплата через QR Manager. Безопасность гарантирована.
          </p>
        </div>
      )}

      {phase.stage === 'paid' && (
        <div className="text-center py-16 space-y-4">
          <div className="text-4xl">✅</div>
          <h1 className="text-xl font-bold">Оплата прошла успешно!</h1>
          <p className="text-muted-foreground">Перенаправляем к билетам...</p>
        </div>
      )}
    </div>
  );
}
