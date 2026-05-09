'use client';

/**
 * /admin/events/[id] — редактирование события.
 * Тот же wizard, но с предзаполнением через useQuery.
 */
import { use } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useEvent } from '@/features/events/admin/api/events';
import { EventWizard } from '@/features/events/admin/components/EventWizard';

export default function EditEventPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();
  const { data: event, isLoading, isError, error } = useEvent(id);

  // Loading
  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <Skeleton className="h-9 w-64" />
          <Skeleton className="mt-2 h-5 w-96" />
        </div>
        <div className="space-y-4">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-32 w-full" />
        </div>
      </div>
    );
  }

  // Error
  if (isError || !event) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">
            Ошибка загрузки
          </h1>
        </div>
        <div className="rounded-lg border border-red-600/30 bg-red-600/10 p-6 text-center">
          <p className="text-red-400">
            {error instanceof Error
              ? error.message
              : 'Не удалось загрузить событие'}
          </p>
          <div className="mt-4 flex justify-center gap-3">
            <Button variant="outline" onClick={() => router.back()}>
              Назад
            </Button>
            <Button onClick={() => router.refresh()}>Повторить</Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">
          Редактирование: {event.title}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {event.status === 'published'
            ? 'Событие опубликовано — некоторые поля заблокированы.'
            : 'Измените информацию о событии.'}
        </p>
      </div>
      <EventWizard event={event} mode="edit" />
    </div>
  );
}