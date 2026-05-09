'use client';

/**
 * /admin/events/[id]/preview — предпросмотр события как на витрине.
 * Показывает карточку события + детали (hero, описание, тарифы).
 */
import { use } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';
import { useEvent } from '@/features/events/admin/api/events';
import { formatKopecks } from '@/lib/utils/money';
import { formatDateTime } from '@/lib/utils/date';
import { cn } from '@/lib/utils/cn';

export default function EventPreviewPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();
  const { data: event, isLoading, isError } = useEvent(id);

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-64 w-full rounded-lg" />
        <Skeleton className="h-8 w-3/4" />
        <Skeleton className="h-4 w-1/2" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }

  if (isError || !event) {
    return (
      <div className="rounded-lg border border-red-600/30 bg-red-600/10 p-6 text-center">
        <p className="text-red-400">Не удалось загрузить событие</p>
        <Button variant="outline" className="mt-3" onClick={() => router.back()}>
          Назад
        </Button>
      </div>
    );
  }

  const schedule = event.schedule;
  const startsAt =
    schedule.type === 'sessions'
      ? schedule.sessions?.[0]?.starts_at
      : schedule.starts_at;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">
            Предпросмотр
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Так событие будет выглядеть на витрине для гостей.
          </p>
        </div>
        <Button variant="outline" onClick={() => router.back()}>
          ← Назад к редактированию
        </Button>
      </div>

      {/* Preview card */}
      <div className="mx-auto max-w-2xl space-y-6">
        {/* Hero */}
        <div
          className={cn(
            'relative overflow-hidden rounded-xl',
            event.image_background_url
              ? 'h-64 sm:h-80'
              : 'h-48 bg-muted',
          )}
        >
          {event.image_background_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={event.image_background_url}
              alt={event.title}
              className="h-full w-full object-cover"
            />
          ) : (
            <div className="flex h-full items-center justify-center text-muted-foreground">
              <p>Нет фонового изображения</p>
            </div>
          )}
          <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/20 to-transparent" />
          <div className="absolute bottom-0 left-0 right-0 p-6">
            <h2 className="text-2xl font-bold text-white sm:text-3xl">
              {event.title}
            </h2>
            <div className="mt-2 flex flex-wrap items-center gap-3 text-sm text-white/80">
              {startsAt && <span>{formatDateTime(startsAt)}</span>}
              {event.location_name && (
                <>
                  <span aria-hidden="true">·</span>
                  <span>{event.location_name}</span>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Description */}
        {event.description_md && (
          <div className="rounded-lg border border-border p-6">
            <h3 className="text-lg font-semibold mb-3">Описание</h3>
            <div className="prose prose-invert prose-sm max-w-none text-muted-foreground whitespace-pre-wrap">
              {event.description_md}
            </div>
          </div>
        )}

        {/* Tariffs */}
        <div className="rounded-lg border border-border p-6">
          <h3 className="text-lg font-semibold mb-4">Тарифы</h3>
          {event.tariffs && event.tariffs.length > 0 ? (
            <div className="space-y-3">
              {event.tariffs
                .filter((t) => t.is_active)
                .map((tariff) => (
                  <div
                    key={tariff.id}
                    className="flex items-center justify-between rounded-lg border border-border p-4"
                  >
                    <div>
                      <p className="font-medium">{tariff.name}</p>
                      {tariff.description && (
                        <p className="text-sm text-muted-foreground mt-0.5">
                          {tariff.description}
                        </p>
                      )}
                      {tariff.capacity_limit !== null && (
                        <p className="text-xs text-muted-foreground mt-1">
                          Осталось мест:{' '}
                          {tariff.capacity_limit - tariff.sold_count} /{' '}
                          {tariff.capacity_limit}
                        </p>
                      )}
                    </div>
                    <div className="text-right">
                      <p className="text-lg font-semibold">
                        {formatKopecks(tariff.price_kopecks)}
                      </p>
                      {tariff.sold_count >= (tariff.capacity_limit ?? Infinity) && (
                        <Badge variant="destructive" className="mt-1">
                          Продано
                        </Badge>
                      )}
                    </div>
                  </div>
                ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">Нет активных тарифов</p>
          )}
        </div>

        {/* Custom fields */}
        {event.custom_fields_schema &&
          event.custom_fields_schema.length > 0 && (
            <div className="rounded-lg border border-border p-6">
              <h3 className="text-lg font-semibold mb-3">
                Дополнительная информация
              </h3>
              <p className="text-sm text-muted-foreground mb-3">
                При бронировании гость заполнит следующие поля:
              </p>
              <ul className="space-y-1.5">
                {event.custom_fields_schema.map((field) => (
                  <li
                    key={field.id}
                    className="flex items-center gap-2 text-sm"
                  >
                    <span className="text-muted-foreground">
                      {field.required ? '●' : '○'}
                    </span>
                    <span>{field.label}</span>
                    <span className="text-xs text-muted-foreground">
                      ({field.type})
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

        {/* Sticky CTA (декоративный) */}
        <div className="sticky bottom-4 rounded-lg border border-border bg-card p-4 shadow-lg">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Цена от</p>
              <p className="text-xl font-semibold">
                {event.price_from_kopecks !== null && event.price_from_kopecks !== undefined
                  ? formatKopecks(event.price_from_kopecks)
                  : '—'}
              </p>
            </div>
            <Button size="lg" disabled>
              Купить билет
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}