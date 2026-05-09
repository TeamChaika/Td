'use client';

/**
 * EventFilters — фильтры для списка событий.
 * Статус (single-select), диапазон дат, поиск по title.
 */
import { useState, useCallback } from 'react';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils/cn';
import type { EventStatus } from '@/types/api';

/** Локальный тип фильтров с single-select статусом. */
interface LocalFilters {
  status?: EventStatus | undefined;
  from?: string;
  to?: string;
  search?: string;
  page?: number;
  per_page?: number;
}

const STATUS_OPTIONS: { value: EventStatus; label: string }[] = [
  { value: 'draft', label: 'Черновик' },
  { value: 'pending_moderation', label: 'На модерации' },
  { value: 'published', label: 'Опубликовано' },
  { value: 'rejected', label: 'Отклонено' },
  { value: 'archived', label: 'Архив' },
];

interface EventFiltersProps {
  filters: LocalFilters;
  onChange: (filters: LocalFilters) => void;
}

export function EventFilters({ filters, onChange }: EventFiltersProps) {
  const [search, setSearch] = useState(filters.search ?? '');

  const selectStatus = useCallback(
    (status: EventStatus) => {
      // Повторный клик по активному — сбрасываем фильтр
      const next = filters.status === status ? undefined : status;
      onChange({ ...filters, status: next, page: 1 });
    },
    [filters, onChange],
  );

  const handleSearch = useCallback(() => {
    onChange({ ...filters, search: search || undefined, page: 1 });
  }, [search, filters, onChange]);

  const clearFilters = useCallback(() => {
    setSearch('');
    onChange({ page: 1, per_page: filters.per_page });
  }, [filters.per_page, onChange]);

  const hasActiveFilters =
    filters.status !== undefined ||
    !!filters.search ||
    !!filters.from ||
    !!filters.to;

  return (
    <div className="space-y-3">
      {/* Search */}
      <div className="flex gap-2">
        <Input
          placeholder="Поиск по названию..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') handleSearch();
          }}
          className="flex-1"
        />
        <Button variant="outline" size="sm" onClick={handleSearch}>
          Найти
        </Button>
      </div>

      {/* Status chips — single select */}
      <div className="flex flex-wrap gap-1.5">
        {STATUS_OPTIONS.map((opt) => {
          const active = filters.status === opt.value;
          return (
            <button
              key={opt.value}
              type="button"
              onClick={() => selectStatus(opt.value)}
              className={cn(
                'rounded-full px-3 py-1 text-xs font-medium transition-colors',
                active
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-muted text-muted-foreground hover:bg-muted/80',
              )}
            >
              {opt.label}
            </button>
          );
        })}
      </div>

      {/* Date range */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
        <div className="space-y-1 flex-1">
          <Label htmlFor="filter-from" className="text-xs">
            С
          </Label>
          <Input
            id="filter-from"
            type="date"
            value={filters.from ?? ''}
            onChange={(e) =>
              onChange({
                ...filters,
                from: e.target.value || undefined,
                page: 1,
              })
            }
          />
        </div>
        <div className="space-y-1 flex-1">
          <Label htmlFor="filter-to" className="text-xs">
            По
          </Label>
          <Input
            id="filter-to"
            type="date"
            value={filters.to ?? ''}
            onChange={(e) =>
              onChange({
                ...filters,
                to: e.target.value || undefined,
                page: 1,
              })
            }
          />
        </div>
        {hasActiveFilters && (
          <Button
            variant="ghost"
            size="sm"
            onClick={clearFilters}
            className="h-10"
          >
            Сбросить
          </Button>
        )}
      </div>
    </div>
  );
}