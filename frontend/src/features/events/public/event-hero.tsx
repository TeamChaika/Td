/**
 * EventHero — hero-секция страницы события.
 * Полноширинное фоновое изображение с оверлеем.
 * На мобильном: изображение сверху, текст снизу.
 * На десктопе: оверлей поверх изображения.
 */
import Image from 'next/image';

import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { formatSchedule } from './schedule-format';
import type { PublicEventDetail } from '@/types/api';

interface EventHeroProps {
  event: PublicEventDetail;
}

export function EventHero({ event }: EventHeroProps) {
  return (
    <section className="relative overflow-hidden bg-muted">
      {/* Background image */}
      {event.image_background_url ? (
        <>
          {/* Mobile: image on top */}
          <div className="relative aspect-[4/3] md:hidden">
            <Image
              src={event.image_background_url}
              alt={event.title}
              fill
              priority
              sizes="100vw"
              className="object-cover"
            />
          </div>
          {/* Desktop: full-width background */}
          <div className="relative hidden aspect-[16/9] md:block lg:aspect-[21/9]">
            <Image
              src={event.image_background_url}
              alt={event.title}
              fill
              priority
              sizes="100vw"
              className="object-cover"
            />
            {/* Overlay */}
            <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/40 to-black/20" />
            <div className="absolute bottom-0 left-0 right-0 p-6 md:p-10 lg:p-14">
              <HeroContent event={event} />
            </div>
          </div>
        </>
      ) : (
        <div className="flex items-center justify-center bg-gradient-to-br from-muted to-card py-16 md:py-24">
          <HeroContent event={event} />
        </div>
      )}

      {/* Mobile: text below image */}
      {event.image_background_url && (
        <div className="p-4 md:hidden">
          <HeroContent event={event} />
        </div>
      )}
    </section>
  );
}

function HeroContent({ event }: { event: PublicEventDetail }) {
  return (
    <div className="mx-auto max-w-5xl">
      {event.is_sold_out && (
        <Badge variant="destructive" className="mb-3 text-sm px-3 py-1">
          Все билеты проданы
        </Badge>
      )}
      <h1 className="text-2xl font-bold tracking-tight text-white md:text-4xl lg:text-5xl">
        {event.title}
      </h1>
      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-white/80 md:text-base">
        <span className="inline-flex items-center gap-1.5">
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5" />
          </svg>
          {formatSchedule(event.schedule)}
        </span>
        {event.location_name && (
          <span className="inline-flex items-center gap-1.5">
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 10.5a3 3 0 11-6 0 3 3 0 016 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1115 0z" />
            </svg>
            {event.location_name}
          </span>
        )}
      </div>
    </div>
  );
}

/** Скелетон hero для состояния загрузки */
export function EventHeroSkeleton() {
  return (
    <section>
      <Skeleton className="aspect-[4/3] w-full rounded-none md:aspect-[16/9] lg:aspect-[21/9]" />
      <div className="mx-auto max-w-5xl p-4 md:p-10 space-y-3">
        <Skeleton className="h-8 w-3/4 md:h-10 md:w-1/2" />
        <div className="flex gap-4">
          <Skeleton className="h-4 w-40" />
          <Skeleton className="h-4 w-32" />
        </div>
      </div>
    </section>
  );
}