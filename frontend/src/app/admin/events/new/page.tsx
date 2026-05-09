'use client';

/**
 * /admin/events/new — wizard создания нового события.
 */
import { EventWizard } from '@/features/events/admin/components/EventWizard';

export default function NewEventPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">
          Новое событие
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Заполните информацию о событии, добавьте тарифы и настройте форму
          бронирования.
        </p>
      </div>
      <EventWizard mode="create" />
    </div>
  );
}