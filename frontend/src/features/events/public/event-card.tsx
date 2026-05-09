/**
 * EventCard — карточка события для каталога.
 * Переиспользуется в публичной витрине и в admin preview (3b).
 */
import Image from 'next/image';
import Link from 'next/link';

import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { formatKopecks } from '@/lib/utils/money';
import { cn } from '@/lib/utils/cn';
import { formatScheduleShort } from './schedule-format';
import type { PublicEventListItem } from '@/types/api';

interface EventCardProps {
  event: PublicEventListItem;
  className?: string;
}

export function EventCard({ event, className }: EventCardProps) {
  return (
    <Link
      href={`/events/${event.slug}`}
      className={cn(
        'group block rounded-xl border border-border bg-card',
        'overflow-hidden transition-all duration-200',
        'hover:shadow-lg hover:shadow-black/20 hover:-translate-y-0.5',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--brand,theme(colors.blue.400))] focus-visible:ring-offset-2 focus-visible:ring-offset-background',
        className,
      )}
    >
      {/* Image */}
      <div className="relative aspect-[4/3] overflow-hidden bg-muted">
        {event.image_card_url ? (
          <Image
            src={event.image_card_url}
            alt={event.title}
            fill
            sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, (max-width: 1280px) 33vw, 25vw"
            className="object-cover transition-transform duration-300 group-hover:scale-105"
            loading="lazy"
          />
        ) : (
          <div className="flex h-full items-center justify-center text-muted-foreground">
            <svg
              className="h-12 w-12 opacity-30"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0022.5 18.75V5.25A2.25 2.25 0 0020.25 3H3.75A2.25 2.25 0 001.5 5.25v13.5A2.25 2.25 0 003.75 21z"
              />
            </svg>
          </div>
        )}

        {/* Sold out overlay */}
        {event.is_sold_out && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/60">
            <Badge variant="destructive" className="text-sm px-4 py-1.5">
              Sold out
            </Badge>
          </div>
        )}
      </div>

      {/* Content */}
      <div className="p-4">
        <h3 className="font-semibold text-foreground line-clamp-2 leading-snug">
          {event.title}
        </h3>

        <p className="mt-1.5 text-sm text-muted-foreground">
          {formatScheduleShort(event.schedule)}
        </p>

        {event.location_name && (
          <p className="mt-0.5 text-sm text-muted-foreground/70 truncate">
            {event.location_name}
          </p>
        )}

        <div className="mt-3 flex items-center justify-between">
          {event.price_from_kopecks !== null ? (
            <span className="text-sm font-medium text-foreground">
              от {formatKopecks(event.price_from_kopecks)}
            </span>
          ) : (
            <span className="text-sm text-muted-foreground">Бесплатно</span>
          )}

          {/* Brand-color underline on hover */}
          <span
            className="h-0.5 w-0 rounded-full transition-all duration-200 group-hover:w-8"
            style={{ backgroundColor: 'var(--brand, #3b82f6)' }}
            aria-hidden
          />
        </div>
      </div>
    </Link>
  );
}

/** Скелетон карточки для состояния загрузки */
export function EventCardSkeleton() {
  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden">
      <Skeleton className="aspect-[4/3] w-full rounded-none" />
      <div className="p-4 space-y-2">
        <Skeleton className="h-5 w-3/4" />
        <Skeleton className="h-4 w-1/2" />
        <Skeleton className="h-4 w-1/3" />
        <div className="flex justify-between pt-1">
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-0.5 w-8" />
        </div>
      </div>
    </div>
  );
}