/**
 * TariffsList — список тарифов события с ценами и статусом sold-out.
 */
import { Badge } from '@/components/ui/badge';
import { formatKopecks } from '@/lib/utils/money';
import { cn } from '@/lib/utils/cn';
import type { PublicTariff } from '@/types/api';

interface TariffsListProps {
  tariffs: PublicTariff[];
  className?: string;
}

export function TariffsList({ tariffs, className }: TariffsListProps) {
  if (tariffs.length === 0) {
    return (
      <p className="text-sm text-muted-foreground italic">
        Информация о тарифах пока не добавлена.
      </p>
    );
  }

  return (
    <div className={cn('space-y-3', className)}>
      {tariffs.map((tariff: PublicTariff) => {
        const isSoldOut =
          tariff.capacity_limit !== null &&
          tariff.sold_count >= tariff.capacity_limit;

        return (
          <div
            key={tariff.id}
            className={cn(
              'flex items-start justify-between gap-4 rounded-lg border border-border bg-card p-4',
              !tariff.is_active && 'opacity-50',
              isSoldOut && 'opacity-60',
            )}
          >
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <h4 className="font-medium text-foreground">{tariff.name}</h4>
                {!tariff.is_active && (
                  <Badge variant="default" className="text-xs">
                    Недоступен
                  </Badge>
                )}
                {isSoldOut && (
                  <Badge variant="destructive" className="text-xs">
                    Sold out
                  </Badge>
                )}
              </div>
              {tariff.description && (
                <p className="mt-1 text-sm text-muted-foreground">
                  {tariff.description}
                </p>
              )}
              {tariff.capacity_limit !== null && (
                <p className="mt-1 text-xs text-muted-foreground/70">
                  Осталось:{' '}
                  {Math.max(0, tariff.capacity_limit - tariff.sold_count)} из{' '}
                  {tariff.capacity_limit}
                </p>
              )}
            </div>
            <div className="shrink-0 text-right">
              <span className="text-lg font-semibold text-foreground">
                {formatKopecks(tariff.price_kopecks)}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}