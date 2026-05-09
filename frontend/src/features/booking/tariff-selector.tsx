'use client';

/**
 * TariffSelector — выбор количества мест по каждому тарифу.
 * Кнопки +/- с проверкой лимита и sold_count.
 */
import type { PublicTariff } from '@/types/api';
import { formatKopecks } from '@/lib/utils/money';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils/cn';

interface TariffSelectorProps {
  tariffs: PublicTariff[];
  /** tariff_id → quantity */
  value: Record<string, number>;
  onChange: (value: Record<string, number>) => void;
}

export function TariffSelector({ tariffs, value, onChange }: TariffSelectorProps) {
  const activeTariffs = tariffs.filter((t) => t.is_active);

  function handleDecrement(tariffId: string) {
    const current = value[tariffId] ?? 0;
    if (current <= 0) return;
    onChange({ ...value, [tariffId]: current - 1 });
  }

  function handleIncrement(tariffId: string, available: number | null) {
    const current = value[tariffId] ?? 0;
    if (available !== null && current >= available) return;
    onChange({ ...value, [tariffId]: current + 1 });
  }

  return (
    <div className="space-y-3">
      {activeTariffs.map((tariff) => {
        const qty = value[tariff.id] ?? 0;
        const available =
          tariff.capacity_limit !== null
            ? Math.max(0, tariff.capacity_limit - tariff.sold_count)
            : null;
        const isSoldOut = available !== null && available <= 0;
        const atMax = available !== null && qty >= available;

        return (
          <div
            key={tariff.id}
            className={cn(
              'flex items-center justify-between rounded-lg border border-border bg-card p-4 gap-3',
              isSoldOut && 'opacity-50',
            )}
          >
            {/* Инфо о тарифе */}
            <div className="min-w-0 flex-1">
              <div className="font-medium text-sm text-foreground truncate">
                {tariff.name}
              </div>
              {tariff.description && (
                <div className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
                  {tariff.description}
                </div>
              )}
              <div className="text-sm font-semibold mt-1" style={{ color: 'var(--brand, hsl(217 91% 60%))' }}>
                {tariff.price_kopecks === 0 ? 'Бесплатно' : formatKopecks(tariff.price_kopecks)}
              </div>
              {isSoldOut && (
                <div className="text-xs text-destructive mt-0.5">Мест нет</div>
              )}
              {!isSoldOut && available !== null && available <= 10 && (
                <div className="text-xs text-amber-600 mt-0.5">
                  Осталось: {available}
                </div>
              )}
            </div>

            {/* Счётчик */}
            <div className="flex items-center gap-2 shrink-0">
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-8 w-8 p-0 text-base"
                disabled={qty <= 0}
                onClick={() => handleDecrement(tariff.id)}
                aria-label={`Уменьшить количество для ${tariff.name}`}
              >
                −
              </Button>
              <span className="w-6 text-center text-sm font-medium tabular-nums">
                {qty}
              </span>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-8 w-8 p-0 text-base"
                disabled={isSoldOut || atMax}
                onClick={() => handleIncrement(tariff.id, available)}
                aria-label={`Увеличить количество для ${tariff.name}`}
              >
                +
              </Button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
