/**
 * EventList — сетка карточек событий.
 * Адаптивная: 1 колонка mobile → 2 sm → 3 lg → 4 xl.
 */
import { EventCard, EventCardSkeleton } from './event-card';
import type { PublicEventListItem } from '@/types/api';

interface EventListProps {
  events: PublicEventListItem[];
  /** Показать скелетоны (состояние загрузки) */
  isLoading?: boolean;
  /** Количество скелетонов */
  skeletonCount?: number;
}

export function EventList({
  events,
  isLoading = false,
  skeletonCount = 8,
}: EventListProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 sm:gap-6">
        {Array.from({ length: skeletonCount }, (_, i) => (
          <EventCardSkeleton key={i} />
        ))}
      </div>
    );
  }

  if (events.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <div
          className="mb-4 flex h-16 w-16 items-center justify-center rounded-full"
          style={{ backgroundColor: 'var(--brand, rgb(59 130 246 / 0.15))' }}
        >
          <svg
            className="h-8 w-8"
            style={{ color: 'var(--brand, rgb(59 130 246))' }}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.5}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5"
            />
          </svg>
        </div>
        <h3 className="text-lg font-medium text-foreground">
          Скоро здесь появятся события
        </h3>
        <p className="mt-1 max-w-sm text-sm text-muted-foreground">
          Мы готовим для вас интересные мероприятия. Загляните позже или
          подпишитесь на обновления.
        </p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 sm:gap-6">
      {events.map((event) => (
        <EventCard key={event.id} event={event} />
      ))}
    </div>
  );
}