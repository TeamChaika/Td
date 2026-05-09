'use client';

/**
 * PromoCodeInput — поле промокода с debounced auto-валидацией.
 *
 * Состояния:
 *  idle    — пусто или менее 6 символов
 *  loading — идёт запрос
 *  valid   — промокод принят (зелёный текст)
 *  invalid — промокод отклонён (красный inline error)
 */
import { useState, useEffect, useRef, useCallback } from 'react';

import type { PromoValidateResponse } from '@/types/api';
import { validatePromoCode } from '@/lib/api/public-reservations';
import { isApiError } from '@/lib/api/errors';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { formatKopecks } from '@/lib/utils/money';
import { cn } from '@/lib/utils/cn';

interface PromoCodeInputProps {
  eventId: string;
  tenantSlug: string;
  /** Email пользователя (для per-user limit проверки) */
  email: string;
  /** Выбранные тарифы (для tariff-specific проверки) */
  items: { tariff_id: string; quantity: number }[];
  /** Вызывается при смене результата (null — промокод убран) */
  onApply: (result: PromoValidateResponse | null) => void;
  disabled?: boolean;
}

type PromoState = 'idle' | 'loading' | 'valid' | 'invalid';

export function PromoCodeInput({
  eventId,
  tenantSlug,
  email,
  items,
  onApply,
  disabled,
}: PromoCodeInputProps) {
  const [code, setCode] = useState('');
  const [state, setState] = useState<PromoState>('idle');
  const [result, setResult] = useState<PromoValidateResponse | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const doValidate = useCallback(
    async (value: string) => {
      if (!value || value.length < 6) {
        setState('idle');
        setResult(null);
        onApply(null);
        return;
      }

      setState('loading');
      try {
        const res = await validatePromoCode(
          { code: value, event_id: eventId, email, items },
          tenantSlug,
        );
        setResult(res);
        if (res.valid) {
          setState('valid');
          onApply(res);
        } else {
          setState('invalid');
          onApply(null);
        }
      } catch (err) {
        const message = isApiError(err) ? err.message : 'Ошибка проверки промокода';
        setResult({ valid: false, error_message: message });
        setState('invalid');
        onApply(null);
      }
    },
    [eventId, tenantSlug, email, items, onApply],
  );

  // Debounce при вводе
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);

    if (code.length >= 6) {
      debounceRef.current = setTimeout(() => {
        void doValidate(code);
      }, 600);
    } else {
      setState('idle');
      setResult(null);
      onApply(null);
    }

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [code, doValidate, onApply]);

  function handleManualApply() {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    void doValidate(code);
  }

  function handleClear() {
    setCode('');
    setState('idle');
    setResult(null);
    onApply(null);
  }

  return (
    <div className="space-y-1.5">
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Input
            type="text"
            placeholder="Промокод"
            value={code}
            onChange={(e) => setCode(e.target.value.toUpperCase())}
            disabled={disabled || state === 'loading'}
            className={cn(
              state === 'valid' && 'border-green-500 focus-visible:ring-green-500',
              state === 'invalid' && 'border-destructive focus-visible:ring-destructive',
            )}
            aria-label="Промокод"
          />
          {/* Иконка статуса */}
          {state === 'loading' && (
            <span className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground text-xs animate-pulse">
              ⟳
            </span>
          )}
          {state === 'valid' && (
            <span className="absolute right-3 top-1/2 -translate-y-1/2 text-green-600 text-sm">
              ✓
            </span>
          )}
        </div>

        {state === 'valid' ? (
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="shrink-0 self-start h-10"
            onClick={handleClear}
          >
            Убрать
          </Button>
        ) : (
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="shrink-0 self-start h-10"
            disabled={disabled || state === 'loading' || code.length < 1}
            onClick={handleManualApply}
          >
            Применить
          </Button>
        )}
      </div>

      {/* Результат валидации */}
      {state === 'valid' && result?.discount_kopecks !== undefined && (
        <p className="text-sm text-green-700 font-medium">
          {result.description
            ? `${result.description}: `
            : result.discount_type === 'percent' && result.discount_value
              ? `Скидка ${result.discount_value / 100}% применена: `
              : 'Скидка применена: '}
          −{formatKopecks(result.discount_kopecks)}
        </p>
      )}
      {state === 'invalid' && result?.error_message && (
        <p className="text-xs text-destructive">{result.error_message}</p>
      )}
    </div>
  );
}
