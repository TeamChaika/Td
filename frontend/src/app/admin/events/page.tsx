'use client';

/**
 * /admin/events — список событий организатора.
 * Таблица с фильтрами, пагинацией и кнопкой создания.
 */
import { useState, useCallback } from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { useToast } from '@/components/ui/toast';
import { useEvents, useDeleteEvent } from '@/features/events/admin/api/events';
import { EventListTable } from '@/features/events/admin/components/EventListTable';
import { EventFilters } from '@/features/events/admin/components/EventFilters';
import { Pagination } from '@/features/events/admin/components/Pagination';
import type { EventsFilters, EventStatus } from '@/types/api';

/** Локальный тип фильтров: статус — одиночный (single-select в UI).
 *  При передаче в API преобразуется в массив. */
interface LocalFilters extends Omit<EventsFilters, 'status'> {
  status?: EventStatus | undefined;
}

export default function EventsListPage() {
  const toast = useToast();
  const [filters, setFilters] = useState<LocalFilters>({
    page: 1,
    per_page: 20,
  });

  // Преобразуем локальные фильтры в API-формат
  const apiFilters: EventsFilters = {
    ...filters,
    status: filters.status ? [filters.status] : undefined,
  };

  const { data, isLoading, isError, error } = useEvents(apiFilters);

  const deleteEvent = useDeleteEvent();

  const handleDelete = useCallback(
    (id: string) => {
      deleteEvent.mutate(id, {
        onSuccess: () => toast.success('Событие перемещено в архив'),
        onError: () => toast.error('Не удалось удалить событие'),
      });
    },
    [deleteEvent, toast],
  );

  const handlePageChange = useCallback(
    (page: number) => {
      setFilters((prev) => ({ ...prev, page }));
    },
    [],
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">События</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Управление событиями и тарифами
          </p>
        </div>
        <Button asChild>
          <Link href="/admin/events/new">+ Создать событие</Link>
        </Button>
      </div>

      {/* Filters */}
      <EventFilters filters={filters} onChange={setFilters} />

      {/* Error state */}
      {isError && (
        <div className="rounded-lg border border-red-600/30 bg-red-600/10 p-6 text-center">
          <p className="text-red-400">
            {error instanceof Error
              ? error.message
              : 'Не удалось загрузить список событий'}
          </p>
          <Button
            variant="outline"
            className="mt-3"
            onClick={() => setFilters({ ...filters })}
          >
            Повторить
          </Button>
        </div>
      )}

      {/* Table */}
      {!isError && (
        <>
          <EventListTable
            events={data?.items ?? []}
            isLoading={isLoading}
            onDelete={handleDelete}
            isDeleting={deleteEvent.isPending}
          />

          {/* Pagination */}
          {data && data.pagination.total_pages > 1 && (
            <Pagination
              page={data.pagination.page}
              totalPages={data.pagination.total_pages}
              onPageChange={handlePageChange}
            />
          )}

          {/* Total count */}
          {data && (
            <p className="text-center text-sm text-muted-foreground">
              Всего событий: {data.pagination.total}
            </p>
          )}
        </>
      )}
    </div>
  );
}