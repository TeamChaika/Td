'use client';

/**
 * BookingForm — форма бронирования билетов.
 *
 * Flow: выбор тарифов → личные данные → кастомные поля → промокод →
 *       согласия → submit → redirect /pay/{reservation_id}
 */
import { useCallback, useId, useMemo, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useRouter } from 'next/navigation';
import { z } from 'zod';

import type { PublicEventDetail, PromoValidateResponse } from '@/types/api';
import { createReservation } from '@/lib/api/public-reservations';
import { isApiError } from '@/lib/api/errors';
import { formatKopecks } from '@/lib/utils/money';
import { useToast } from '@/components/ui/toast';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { TariffSelector } from './tariff-selector';
import { CustomFieldsForm } from './custom-fields-form';
import { PromoCodeInput } from './promo-code-input';
import { PhoneInput } from './phone-input';

// ---- Zod-схема ----

const bookingSchema = z.object({
  first_name: z.string().min(2, 'Введите имя (минимум 2 символа)'),
  last_name: z.string().min(2, 'Введите фамилию (минимум 2 символа)'),
  email: z.string().email('Введите корректный email'),
  phone: z.string().min(10, 'Введите корректный телефон'),
  items: z.record(z.string(), z.number().int().min(0)),
  custom_fields: z.record(z.string(), z.unknown()).optional(),
  consent_privacy: z.literal(true, {
    errorMap: () => ({ message: 'Необходимо согласие на обработку данных' }),
  }),
  consent_offer: z.literal(true, {
    errorMap: () => ({ message: 'Необходимо согласие с офертой' }),
  }),
});

type BookingFormData = z.infer<typeof bookingSchema>;

// ---- Компонент ----

interface BookingFormProps {
  event: PublicEventDetail;
  tenantSlug: string;
}

export function BookingForm({ event, tenantSlug }: BookingFormProps) {
  const router = useRouter();
  const toast = useToast();

  const [promoResult, setPromoResult] = useState<PromoValidateResponse | null>(null);

  // Стабильный idempotency_key: генерируется один раз при mount
  const idempotencyKey = useId();

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    setError,
    control,
    formState: { errors, isSubmitting },
  } = useForm<BookingFormData>({
    resolver: zodResolver(bookingSchema),
    defaultValues: {
      items: {},
      consent_privacy: undefined,
      consent_offer: undefined,
    },
  });

  const itemsValue = watch('items');
  const emailValue = watch('email');

  // Расчёт сумм
  const { subtotal, discount, total } = useMemo(() => {
    let sub = 0;
    for (const tariff of event.tariffs) {
      const qty = itemsValue?.[tariff.id] ?? 0;
      if (qty > 0) sub += tariff.price_kopecks * qty;
    }
    const disc = promoResult?.valid ? (promoResult.discount_kopecks ?? 0) : 0;
    return { subtotal: sub, discount: disc, total: Math.max(0, sub - disc) };
  }, [itemsValue, event.tariffs, promoResult]);

  const hasItems = useMemo(
    () => Object.values(itemsValue ?? {}).some((q) => q > 0),
    [itemsValue],
  );

  // Обработчик промокода
  const handlePromoApply = useCallback(
    (result: PromoValidateResponse | null) => {
      setPromoResult(result);
    },
    [],
  );

  // Submit
  async function onSubmit(data: BookingFormData) {
    // Собираем items с qty > 0
    const items = Object.entries(data.items)
      .filter(([, qty]) => qty > 0)
      .map(([tariff_id, quantity]) => ({ tariff_id, quantity }));

    if (items.length === 0) {
      setError('root', { message: 'Выберите хотя бы один билет' });
      return;
    }

    try {
      const reservation = await createReservation(
        {
          event_id: event.id,
          first_name: data.first_name,
          last_name: data.last_name,
          email: data.email,
          phone: data.phone,
          items,
          custom_fields: data.custom_fields,
          promo_code: promoResult?.valid ? promoResult.code : undefined,
          consent_privacy: data.consent_privacy,
          consent_offer: data.consent_offer,
        },
        tenantSlug,
        idempotencyKey,
      );

      router.push(`/pay/${reservation.id}`);
    } catch (err) {
      if (isApiError(err)) {
        if (err.code === 'email_blocked') {
          setError('email', {
            message: 'Этот email-адрес недоступен для бронирования',
          });
        } else if (err.code === 'capacity_exceeded') {
          setError('root', { message: 'К сожалению, свободных мест больше нет' });
          toast.error('Места закончились — попробуйте другой тариф');
        } else {
          setError('root', { message: err.message });
          toast.error(err.message);
        }
      } else {
        setError('root', { message: 'Произошла ошибка. Попробуйте ещё раз.' });
        toast.error('Произошла ошибка. Попробуйте ещё раз.');
      }
    }
  }

  return (
    <form
      onSubmit={handleSubmit(onSubmit)}
      noValidate
      className="pb-28 sm:pb-0"
    >
      <div className="space-y-8">
        {/* 1. Тарифы */}
        <section>
          <h2 className="text-lg font-semibold mb-3">Выберите билеты</h2>
          <TariffSelector
            tariffs={event.tariffs}
            value={itemsValue ?? {}}
            onChange={(v) => setValue('items', v)}
          />
          {!hasItems && errors.root && (
            <p className="mt-2 text-xs text-destructive">
              {errors.root.message}
            </p>
          )}
        </section>

        {/* 2. Личные данные */}
        <section>
          <h2 className="text-lg font-semibold mb-3">Ваши данные</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="first_name">Имя *</Label>
              <Input
                id="first_name"
                placeholder="Иван"
                {...register('first_name')}
                aria-invalid={!!errors.first_name}
                className={errors.first_name ? 'border-destructive' : ''}
              />
              {errors.first_name && (
                <p className="text-xs text-destructive">
                  {errors.first_name.message}
                </p>
              )}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="last_name">Фамилия *</Label>
              <Input
                id="last_name"
                placeholder="Петров"
                {...register('last_name')}
                aria-invalid={!!errors.last_name}
                className={errors.last_name ? 'border-destructive' : ''}
              />
              {errors.last_name && (
                <p className="text-xs text-destructive">
                  {errors.last_name.message}
                </p>
              )}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="email">Email *</Label>
              <Input
                id="email"
                type="email"
                placeholder="ivan@example.com"
                {...register('email')}
                aria-invalid={!!errors.email}
                className={errors.email ? 'border-destructive' : ''}
              />
              {errors.email && (
                <p className="text-xs text-destructive">
                  {errors.email.message}
                </p>
              )}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="phone">Телефон *</Label>
              <PhoneInput
                value={watch('phone') ?? ''}
                onChange={(v) => setValue('phone', v, { shouldValidate: true })}
                error={errors.phone?.message}
              />
            </div>
          </div>
        </section>

        {/* 3. Кастомные поля (если есть) */}
        {event.custom_fields_schema && event.custom_fields_schema.length > 0 && (
          <section>
            <h2 className="text-lg font-semibold mb-3">Дополнительно</h2>
            <CustomFieldsForm
              fields={event.custom_fields_schema}
              control={control}
              errors={errors}
              fieldPath="custom_fields"
            />
          </section>
        )}

        {/* 4. Промокод */}
        <section>
          <h2 className="text-lg font-semibold mb-3">Промокод</h2>
          <PromoCodeInput
            eventId={event.id}
            tenantSlug={tenantSlug}
            email={emailValue ?? ''}
            items={Object.entries(itemsValue ?? {})
              .filter(([, qty]) => qty > 0)
              .map(([tariff_id, quantity]) => ({ tariff_id, quantity }))}
            onApply={handlePromoApply}
            disabled={isSubmitting}
          />
        </section>

        {/* 5. Согласия */}
        <section className="space-y-3">
          <label className="flex items-start gap-3 cursor-pointer">
            <input
              type="checkbox"
              className="mt-0.5 h-4 w-4 shrink-0 rounded border-border accent-primary"
              {...register('consent_offer')}
            />
            <span className="text-sm text-muted-foreground">
              Я согласен с{' '}
              <a href="/terms" target="_blank" className="underline hover:text-foreground">
                офертой
              </a>
            </span>
          </label>
          {errors.consent_offer && (
            <p className="text-xs text-destructive pl-7">
              {errors.consent_offer.message}
            </p>
          )}

          <label className="flex items-start gap-3 cursor-pointer">
            <input
              type="checkbox"
              className="mt-0.5 h-4 w-4 shrink-0 rounded border-border accent-primary"
              {...register('consent_privacy')}
            />
            <span className="text-sm text-muted-foreground">
              Я согласен на{' '}
              <a href="/privacy" target="_blank" className="underline hover:text-foreground">
                обработку персональных данных
              </a>
            </span>
          </label>
          {errors.consent_privacy && (
            <p className="text-xs text-destructive pl-7">
              {errors.consent_privacy.message}
            </p>
          )}
        </section>

        {/* Ошибка root */}
        {errors.root && (
          <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
            {errors.root.message}
          </div>
        )}

        {/* Кнопка submit — только для desktop (на мобиле в sticky bar) */}
        <div className="hidden sm:block">
          <SubmitBar
            total={total}
            discount={discount}
            subtotal={subtotal}
            isSubmitting={isSubmitting}
            hasItems={hasItems}
          />
        </div>
      </div>

      {/* Sticky bottom bar — только mobile */}
      <div className="fixed bottom-0 left-0 right-0 z-40 border-t border-border bg-card/95 backdrop-blur-sm p-4 sm:hidden">
        <SubmitBar
          total={total}
          discount={discount}
          subtotal={subtotal}
          isSubmitting={isSubmitting}
          hasItems={hasItems}
          compact
        />
      </div>
    </form>
  );
}

// ---- Sticky/inline submit bar ----

interface SubmitBarProps {
  total: number;
  subtotal: number;
  discount: number;
  isSubmitting: boolean;
  hasItems: boolean;
  compact?: boolean;
}

function SubmitBar({
  total,
  discount,
  isSubmitting,
  hasItems,
  compact,
}: SubmitBarProps) {
  return (
    <div className={compact ? 'flex items-center gap-3' : 'space-y-3'}>
      {!compact && discount > 0 && (
        <div className="text-sm text-muted-foreground">
          Скидка: −{formatKopecks(discount)}
        </div>
      )}

      <div className={compact ? 'flex-1' : ''}>
        {compact ? (
          <div className="text-sm font-semibold">
            {hasItems ? formatKopecks(total) : 'Выберите билеты'}
          </div>
        ) : (
          <div className="text-xl font-bold">
            Итого: {hasItems ? formatKopecks(total) : '—'}
          </div>
        )}
      </div>

      <Button
        type="submit"
        size={compact ? 'default' : 'lg'}
        disabled={isSubmitting || !hasItems}
        className={compact ? 'shrink-0' : 'w-full'}
        style={{
          backgroundColor: 'var(--brand, hsl(217 91% 60%))',
          color: 'white',
        }}
      >
        {isSubmitting ? 'Оформляем...' : 'Перейти к оплате'}
      </Button>
    </div>
  );
}
