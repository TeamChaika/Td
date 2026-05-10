'use client';

/**
 * EventListTable — таблица событий.
 * Колонки: thumbnail | title | дата | цена «от» | продано/всего | статус | действия.
 */
import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { ConfirmDialog } from '@/components/ui/confirm-dialog';
import { EventStatusBadge } from './EventStatusBadge';
import { formatKopecks } from '@/lib/utils/money';
import { formatDateTime } from '@/lib/utils/date';
import type { EventItem } from '@/types/api';

interface EventListTableProps {
  events: EventItem[];
  isLoading: boolean;
  onDelete: (id: string) => void;
  isDeleting?: boolean;
}

export function EventListTable({
  events,
  isLoading,
  onDelete,
}: EventListTableProps) {
  const router = useRouter();
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);

  // Loading skeleton
  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="flex items-center gap-4 rounded-lg border border-border p-4">
            <Skeleton className="h-12 w-20 rounded" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-3 w-1/2" />
            </div>
            <Skeleton className="h-6 w-20 rounded-full" />
          </div>
        ))}
      </div>
    );
  }

  // Empty state
  if (events.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-border p-12 text-center">
        <svg
          className="mx-auto h-12 w-12 text-muted-foreground"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
          />
        </svg>
        <h3 className="mt-4 text-lg font-medium">Нет событий</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          {events.length === 0 && 'Создайте первое событие, чтобы начать продавать билеты.'}
        </p>
        <Button asChild className="mt-6">
          <Link href="/admin/events/new">Создать первое событие</Link>
        </Button>
      </div>
    );
  }

  return (
    <>
      {/* Mobile: cards */}
      <div className="space-y-3 md:hidden">
        {events.map((event) => (
          <div
            key={event.id}
            className="rounded-lg border border-border p-4 space-y-3"
          >
            <div className="flex items-start gap-3">
              {event.image_card_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={event.image_card_url}
                  alt={event.title}
                  className="h-16 w-24 shrink-0 rounded object-cover"
                />
              ) : (
                <div className="h-16 w-24 shrink-0 rounded bg-muted flex items-center justify-center text-xs text-muted-foreground">
                  Нет фото
                </div>
              )}
              <div className="min-w-0 flex-1">
                <Link
                  href={`/admin/events/${event.id}`}
                  className="font-medium hover:text-primary truncate block"
                >
                  {event.title}
                </Link>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {formatDateTime(event.schedule.starts_at ?? '')}
                </p>
                <div className="flex items-center gap-2 mt-1">
                  <EventStatusBadge status={event.status} />
                  {event.price_from_kopecks !== null && event.price_from_kopecks !== undefined && (
                    <span className="text-xs text-muted-foreground">
                      от {formatKopecks(event.price_from_kopecks)}
                    </span>
                  )}
                </div>
              </div>
            </div>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                className="flex-1"
                onClick={() => router.push(`/admin/events/${event.id}`)}
              >
                Ред.
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="flex-1"
                onClick={() => router.push(`/admin/events/${event.id}/preview`)}
              >
                Превью
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="text-red-400"
                onClick={() => setDeleteId(event.id)}
              >
                Удалить
              </Button>
            </div>
          </div>
        ))}
      </div>

      {/* Desktop: table */}
      <div className="hidden md:block overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-muted-foreground">
              <th className="pb-3 pl-4 pr-2 font-medium w-24">Фото</th>
              <th className="pb-3 px-2 font-medium">Название</th>
              <th className="pb-3 px-2 font-medium">Дата</th>
              <th className="pb-3 px-2 font-medium">Цена от</th>
              <th className="pb-3 px-2 font-medium">Продано</th>
              <th className="pb-3 px-2 font-medium">Статус</th>
              <th className="pb-3 pr-4 pl-2 font-medium w-10"></th>
            </tr>
          </thead>
          <tbody>
            {events.map((event) => (
              <tr
                key={event.id}
                className="border-b border-border/50 hover:bg-muted/30 transition-colors"
              >
                {/* Thumbnail */}
                <td className="py-3 pl-4 pr-2">
                  {event.image_card_url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={event.image_card_url}
                      alt={event.title}
                      className="h-12 w-20 rounded object-cover"
                    />
                  ) : (
                    <div className="h-12 w-20 rounded bg-muted flex items-center justify-center text-xs text-muted-foreground">
                      —
                    </div>
                  )}
                </td>

                {/* Title */}
                <td className="py-3 px-2">
                  <Link
                    href={`/admin/events/${event.id}`}
                    className="font-medium hover:text-primary"
                  >
                    {event.title}
                  </Link>
                  <p className="text-xs text-muted-foreground truncate max-w-xs">
                    {event.location_name}
                  </p>
                </td>

                {/* Date */}
                <td className="py-3 px-2 whitespace-nowrap text-muted-foreground">
                  {formatDateTime(event.schedule.starts_at ?? '')}
                </td>

                {/* Price from */}
                <td className="py-3 px-2 whitespace-nowrap">
                  {event.price_from_kopecks !== null && event.price_from_kopecks !== undefined
                    ? formatKopecks(event.price_from_kopecks)
                    : '—'}
                </td>

                {/* Sold / total */}
                <td className="py-3 px-2 whitespace-nowrap text-muted-foreground">
                  {event.sold_count}
                  {event.capacity_policy?.type === 'total' ? ` / ${(event.capacity_policy as any).limit ?? '?'}` : ''}
                  {event.capacity_policy?.type === 'hybrid' ? ` / ${(event.capacity_policy as any).total ?? '?'}` : ''}
                </td>

                {/* Status */}
                <td className="py-3 px-2">
                  <EventStatusBadge status={event.status} />
                </td>

                {/* Actions menu */}
                <td className="py-3 pr-4 pl-2 relative">
                  <button
                    type="button"
                    onClick={() =>
                      setMenuOpenId(menuOpenId === event.id ? null : event.id)
                    }
                    className="rounded p-1 hover:bg-accent"
                    aria-label="Действия"
                  >
                    <svg
                      className="h-4 w-4"
                      fill="currentColor"
                      viewBox="0 0 16 16"
                    >
                      <circle cx="8" cy="3" r="1.5" />
                      <circle cx="8" cy="8" r="1.5" />
                      <circle cx="8" cy="13" r="1.5" />
                    </svg>
                  </button>

                  {menuOpenId === event.id && (
                    <>
                      <div
                        className="fixed inset-0 z-10"
                        onClick={() => setMenuOpenId(null)}
                      />
                      <div className="absolute right-0 top-full z-20 mt-1 w-44 rounded-md border border-border bg-card shadow-lg py-1">
                        <button
                          type="button"
                          className="w-full px-4 py-2 text-left text-sm hover:bg-accent"
                          onClick={() => {
                            setMenuOpenId(null);
                            router.push(`/admin/events/${event.id}`);
                          }}
                        >
                          Редактировать
                        </button>
                        <button
                          type="button"
                          className="w-full px-4 py-2 text-left text-sm hover:bg-accent"
                          onClick={() => {
                            setMenuOpenId(null);
                            router.push(`/admin/events/${event.id}/preview`);
                          }}
                        >
                          Предпросмотр
                        </button>
                        <button
                          type="button"
                          className="w-full px-4 py-2 text-left text-sm text-red-400 hover:bg-accent"
                          onClick={() => {
                            setMenuOpenId(null);
                            setDeleteId(event.id);
                          }}
                        >
                          Удалить
                        </button>
                      </div>
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Delete confirm */}
      <ConfirmDialog
        open={!!deleteId}
        onOpenChange={(open) => {
          if (!open) setDeleteId(null);
        }}
        title="Удалить событие?"
        description="Событие будет перемещено в архив. Это действие можно отменить."
        confirmLabel="Удалить"
        variant="destructive"
        onConfirm={() => {
          if (deleteId) onDelete(deleteId);
          setDeleteId(null);
        }}
      />
    </>
  );
}