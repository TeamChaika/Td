/**
 * BuyTicketCTA — sticky-кнопка «Купить билет».
 * На мобильном: прижата к низу экрана.
 * На десктопе: в правой колонке.
 */
import Link from 'next/link';

import { Button } from '@/components/ui/button';
import { formatKopecks } from '@/lib/utils/money';
import { cn } from '@/lib/utils/cn';

interface BuyTicketCTAProps {
  eventSlug: string;
  priceFromKopecks: number | null;
  isSoldOut: boolean;
  /** Вариант отображения: sticky-bottom (мобильный) или inline (десктоп) */
  variant?: 'sticky-bottom' | 'inline';
  className?: string;
}

export function BuyTicketCTA({
  eventSlug,
  priceFromKopecks,
  isSoldOut,
  variant = 'inline',
  className,
}: BuyTicketCTAProps) {
  if (isSoldOut) {
    return (
      <div
        className={cn(
          variant === 'sticky-bottom' &&
            'fixed bottom-0 left-0 right-0 z-40 border-t border-border bg-card/95 backdrop-blur-sm p-4 md:hidden',
          className,
        )}
      >
        <Button disabled size="lg" className="w-full min-h-11">
          Все билеты проданы
        </Button>
      </div>
    );
  }

  const priceLabel =
    priceFromKopecks !== null
      ? `от ${formatKopecks(priceFromKopecks)}`
      : 'Бесплатно';

  return (
    <div
      className={cn(
        variant === 'sticky-bottom' &&
          'fixed bottom-0 left-0 right-0 z-40 border-t border-border bg-card/95 backdrop-blur-sm p-4 md:hidden',
        className,
      )}
    >
      <Button
        asChild
        size="lg"
        className="w-full min-h-11"
        style={{
          backgroundColor: 'var(--brand, hsl(217 91% 60%))',
          color: 'white',
        }}
      >
        <Link href={`/events/${eventSlug}/book`}>
          Купить билет &middot; {priceLabel}
        </Link>
      </Button>
    </div>
  );
}