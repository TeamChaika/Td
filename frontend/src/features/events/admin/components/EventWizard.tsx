'use client';

/**
 * EventWizard — главный stepper-компонент создания/редактирования события.
 * 3 шага: Основное → Тарифы → Поля формы.
 *
 * BLOCKER 1 fix: после create/update синхронизирует тарифы (create/update/delete).
 * BLOCKER 2 fix: /images (plural).
 * BLOCKER 3 fix: sort_order в тарифах.
 * WARNING 1 fix: slugTouched защищает ручной slug от auto-slug.
 */
import { useState, useCallback, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { useForm, FormProvider } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useQueryClient } from '@tanstack/react-query';

import { Button } from '@/components/ui/button';
import { Spinner } from '@/components/ui/spinner';
import { useToast } from '@/components/ui/toast';
import { api } from '@/lib/api/client';
import { isApiError } from '@/lib/api/errors';
import { cn } from '@/lib/utils/cn';
import { useSession } from '@/lib/auth/use-session';

import { ScheduleEditor } from './ScheduleEditor';
import { CapacityPolicyEditor } from './CapacityPolicyEditor';
import { TariffsEditor } from './TariffsEditor';
import { CustomFieldsEditor } from './CustomFieldsEditor';
import { BookingFormPreview } from './BookingFormPreview';
import { ImageUpload } from './ImageUpload';

import {
  eventWizardSchema,
  step1Schema,
  step2Schema,
  step3Schema,
  slugify,
  generateSessionId,
  type EventWizardFormData,
  type TariffFormData,
} from '../schemas';
import type { EventItem, EventDetailResponse, EventTariff } from '@/types/api';

const STEPS = [
  { id: 1, label: 'Основное' },
  { id: 2, label: 'Тарифы' },
  { id: 3, label: 'Поля формы' },
] as const;

interface EventWizardProps {
  event?: EventDetailResponse;
  mode: 'create' | 'edit';
}

/** Преобразовать тариф формы в API-запрос (рубли → копейки). */
function tariffToCreatePayload(t: TariffFormData, index: number) {
  return {
    name: t.name,
    description: t.description || undefined,
    price_kopecks: Math.round(t.price_rub * 100),
    capacity_limit: t.capacity_limit ?? undefined,
    is_active: t.is_active,
    sort_order: t.sort_order ?? index,
  };
}

function tariffToUpdatePayload(t: TariffFormData, index: number) {
  return {
    name: t.name,
    description: t.description || undefined,
    price_kopecks: Math.round(t.price_rub * 100),
    capacity_limit: t.capacity_limit ?? undefined,
    is_active: t.is_active,
    sort_order: t.sort_order ?? index,
  };
}

export function EventWizard({ event, mode }: EventWizardProps) {
  const router = useRouter();
  const toast = useToast();
  const queryClient = useQueryClient();
  const { organization } = useSession();
  const [step, setStep] = useState(1);
  const [cardFile, setCardFile] = useState<File | null>(null);
  const [bgFile, setBgFile] = useState<File | null>(null);
  const [isDraftSaving, setIsDraftSaving] = useState(false);
  const [isUploadingImages, setIsUploadingImages] = useState(false);
  const [slugTouched, setSlugTouched] = useState(false);

  const isEdit = mode === 'edit';

  // Инициализация формы
  const methods = useForm<EventWizardFormData>({
    resolver: zodResolver(eventWizardSchema),
    defaultValues: event
      ? {
          title: event.title,
          slug: event.slug,
          description_md: event.description_md ?? '',
          location_name: event.location_name ?? '',
          location_address: event.location_address ?? '',
          schedule: event.schedule as EventWizardFormData['schedule'],
          capacity_policy:
            event.capacity_policy as EventWizardFormData['capacity_policy'],
          tariffs: ((event.tariffs ?? []) as EventTariff[]).map((t, i) => ({
            backendId: t.id,
            name: t.name,
            description: t.description ?? '',
            price_rub: t.price_kopecks / 100,
            capacity_limit: t.capacity_limit,
            is_active: t.is_active,
            sort_order: (t as Record<string, unknown>).sort_order as number ?? i,
          })),
          custom_fields:
            (event.custom_fields_schema as EventWizardFormData['custom_fields']) ??
            [],
        }
      : {
          title: '',
          slug: '',
          description_md: '',
          location_name: '',
          location_address: '',
          schedule: {
            type: 'single',
            starts_at: '',
            ends_at: '',
          },
          capacity_policy: { type: 'unlimited' },
          tariffs: [
            {
              name: '',
              description: '',
              price_rub: 0,
              capacity_limit: null,
              is_active: true,
              sort_order: 0,
            },
          ],
          custom_fields: [],
        },
  });

  const { handleSubmit, watch, setValue, trigger } = methods;

  const title = watch('title');
  const slug = watch('slug');

  // Auto-slug из title (только если slug не трогали вручную)
  useEffect(() => {
    if (!slugTouched && title && !isEdit) {
      setValue('slug', slugify(title));
    }
  }, [title, setValue, isEdit, slugTouched]);

  const handleSlugChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setSlugTouched(true);
      setValue('slug', e.target.value);
    },
    [setValue],
  );

  // ---- Helpers ----

  function formDataToPayload(data: EventWizardFormData) {
    return {
      title: data.title,
      slug: data.slug,
      description_md: data.description_md || undefined,
      location_name: data.location_name,
      location_address: data.location_address || undefined,
      schedule: data.schedule,
      capacity_policy: data.capacity_policy,
      custom_fields_schema:
        data.custom_fields && (data.custom_fields as unknown[]).length > 0
          ? data.custom_fields
          : undefined,
    };
  }

  /** Загрузить картинки для события. */
  const uploadImages = useCallback(
    async (eventId: string) => {
      const uploads: Promise<unknown>[] = [];
      if (cardFile) {
        const fd = new FormData();
        fd.append('file', cardFile);
        fd.append('kind', 'card');
        uploads.push(
          api(`/api/v1/organizer/events/${eventId}/images`, {
            method: 'POST',
            body: fd,
          }).catch((err) => {
            const msg = isApiError(err)
              ? err.message
              : 'Не удалось загрузить картинку карточки';
            throw new Error(msg);
          }),
        );
      }
      if (bgFile) {
        const fd = new FormData();
        fd.append('file', bgFile);
        fd.append('kind', 'background');
        uploads.push(
          api(`/api/v1/organizer/events/${eventId}/images`, {
            method: 'POST',
            body: fd,
          }).catch((err) => {
            const msg = isApiError(err)
              ? err.message
              : 'Не удалось загрузить фоновое изображение';
            throw new Error(msg);
          }),
        );
      }
      if (uploads.length > 0) {
        setIsUploadingImages(true);
        try {
          await Promise.all(uploads);
          toast.success('Изображения загружены');
        } catch (err) {
          toast.error(
            err instanceof Error
              ? err.message
              : 'Изображения не загрузились. Вы можете добавить их позже.',
          );
        } finally {
          setIsUploadingImages(false);
        }
      }
    },
    [cardFile, bgFile, toast],
  );

  /**
   * Синхронизировать тарифы после создания/обновления события.
   * - Новые (без backendId) → POST
   * - Изменённые (с backendId) → PATCH
   * - Удалённые (backendId есть в event.tariffs, нет в форме) → DELETE
   */
  const syncTariffs = useCallback(
    async (eventId: string, formTariffs: TariffFormData[]) => {
      const existingTariffs = (event?.tariffs ?? []) as EventTariff[];
      const existingIds = new Set(existingTariffs.map((t) => t.id));

      // Тарифы из формы с backendId
      const formBackendIds = new Set(
        formTariffs.filter((t) => t.backendId).map((t) => t.backendId!),
      );

      // Удалённые: есть в existing, нет в форме
      const toDelete = existingTariffs.filter(
        (t) => !formBackendIds.has(t.id),
      );

      let createdCount = 0;
      let updatedCount = 0;
      let deletedCount = 0;
      let errorCount = 0;
      const totalOps =
        formTariffs.filter((t) => !t.backendId).length +
        formTariffs.filter((t) => t.backendId).length +
        toDelete.length;

      // 1. Удаляем
      for (const t of toDelete) {
        try {
          await api(`/api/v1/organizer/tariffs/${t.id}`, { method: 'DELETE' });
          deletedCount++;
        } catch {
          errorCount++;
        }
      }

      // 2. Создаём новые (последовательно, чтобы знать какие упали)
      for (let i = 0; i < formTariffs.length; i++) {
        const t = formTariffs[i]!;
        if (t.backendId) continue; // пропускаем существующие
        try {
          await api(`/api/v1/organizer/events/${eventId}/tariffs`, {
            method: 'POST',
            body: tariffToCreatePayload(t, i),
          });
          createdCount++;
        } catch {
          errorCount++;
        }
      }

      // 3. Обновляем изменённые
      for (let i = 0; i < formTariffs.length; i++) {
        const t = formTariffs[i]!;
        if (!t.backendId) continue;
        const existing = existingTariffs.find((e) => e.id === t.backendId);
        if (!existing) continue;

        // Проверяем, изменились ли данные
        const priceKopecks = Math.round(t.price_rub * 100);
        const changed =
          existing.name !== t.name ||
          existing.description !== (t.description || null) ||
          existing.price_kopecks !== priceKopecks ||
          existing.capacity_limit !== (t.capacity_limit ?? null) ||
          existing.is_active !== t.is_active ||
          (existing as Record<string, unknown>).sort_order !== (t.sort_order ?? i);

        if (!changed) continue;

        try {
          await api(`/api/v1/organizer/tariffs/${t.backendId}`, {
            method: 'PATCH',
            body: tariffToUpdatePayload(t, i),
          });
          updatedCount++;
        } catch {
          errorCount++;
        }
      }

      // Инвалидируем кэш
      queryClient.invalidateQueries({ queryKey: ['events'] });
      queryClient.invalidateQueries({ queryKey: ['tariffs'] });

      // Сообщаем результат
      if (errorCount > 0) {
        const successCount = createdCount + updatedCount + deletedCount;
        toast.error(
          `Тарифы: ${successCount}/${totalOps} сохранены, ${errorCount} с ошибкой. Проверьте список тарифов.`,
        );
      } else if (totalOps > 0) {
        toast.success(
          `Тарифы сохранены (создано: ${createdCount}, обновлено: ${updatedCount}, удалено: ${deletedCount})`,
        );
      }
    },
    [event, toast, queryClient],
  );

  // ---- Handlers ----

  const handleSubmitFinal = useCallback(
    async (data: EventWizardFormData) => {
      let eventId: string;

      if (isEdit && event) {
        // Обновляем событие
        try {
          const payload = formDataToPayload(data);
          const updated = await api<EventItem>(
            `/api/v1/organizer/events/${event.id}`,
            { method: 'PATCH', body: payload },
          );
          eventId = updated.id;
          toast.success('Событие обновлено');
        } catch (err) {
          toast.error(
            isApiError(err) ? err.message : 'Не удалось обновить событие',
          );
          return;
        }
      } else {
        // Создаём
        try {
          const payload = formDataToPayload(data);
          const created = await api<EventItem>('/api/v1/organizer/events', {
            method: 'POST',
            body: payload,
          });
          eventId = created.id;
          toast.success('Событие создано');
        } catch (err) {
          toast.error(
            isApiError(err) ? err.message : 'Не удалось создать событие',
          );
          return;
        }
      }

      // Синхронизируем тарифы
      await syncTariffs(eventId, data.tariffs);

      // Загружаем картинки
      await uploadImages(eventId);

      router.push('/admin/events');
    },
    [isEdit, event, toast, router, syncTariffs, uploadImages],
  );

  const handleSubmitForModeration = useCallback(async () => {
    const data = methods.getValues();
    let eventId = event?.id;

    // Создаём или обновляем событие
    if (!eventId) {
      try {
        const payload = formDataToPayload(data);
        const created = await api<EventItem>('/api/v1/organizer/events', {
          method: 'POST',
          body: payload,
        });
        eventId = created.id;
      } catch (err) {
        toast.error(
          isApiError(err) ? err.message : 'Не удалось создать событие',
        );
        return;
      }
    } else {
      try {
        const payload = formDataToPayload(data);
        await api(`/api/v1/organizer/events/${eventId}`, {
          method: 'PATCH',
          body: payload,
        });
      } catch (err) {
        toast.error(
          isApiError(err) ? err.message : 'Не удалось обновить событие',
        );
        return;
      }
    }

    // Синхронизируем тарифы (обязательно перед submit)
    await syncTariffs(eventId, data.tariffs);

    // Загружаем картинки
    await uploadImages(eventId);

    // Отправляем на модерацию
    try {
      await api(`/api/v1/organizer/events/${eventId}/submit`, {
        method: 'POST',
      });
      toast.success('Событие отправлено на модерацию');
      router.push('/admin/events');
    } catch (err) {
      toast.error(
        isApiError(err) ? err.message : 'Не удалось отправить на модерацию',
      );
      // Событие создано, тарифы сохранены — редиректим на редактирование
      router.push(`/admin/events/${eventId}`);
    }
  }, [methods, event, toast, router, syncTariffs, uploadImages]);

  /** Сохранить черновик. */
  const saveDraft = useCallback(async () => {
    const data = methods.getValues();
    const payload = formDataToPayload(data);

    if (!event?.id && mode === 'create') {
      try {
        const created = await api<EventItem>('/api/v1/organizer/events', {
          method: 'POST',
          body: payload,
        });
        toast.success('Черновик сохранён');
        router.replace(`/admin/events/${created.id}`);
      } catch (err) {
        toast.error(
          isApiError(err) ? err.message : 'Не удалось сохранить черновик',
        );
      }
      return;
    }

    if (!event?.id) return;
    setIsDraftSaving(true);
    try {
      await api(`/api/v1/organizer/events/${event.id}`, {
        method: 'PATCH',
        body: payload,
      });
      toast.success('Черновик сохранён');
    } catch (err) {
      toast.error(
        isApiError(err) ? err.message : 'Не удалось сохранить черновик',
      );
    } finally {
      setIsDraftSaving(false);
    }
  }, [event, mode, methods, toast, router]);

  const validateStep = useCallback(
    async (stepNum: number): Promise<boolean> => {
      let schema;
      switch (stepNum) {
        case 1:
          schema = step1Schema;
          break;
        case 2:
          schema = step2Schema;
          break;
        case 3:
          schema = step3Schema;
          break;
        default:
          return true;
      }
      const result = await trigger(
        Object.keys(schema.shape) as (keyof EventWizardFormData)[],
      );
      return result;
    },
    [trigger],
  );

  const handleNext = useCallback(async () => {
    const valid = await validateStep(step);
    if (valid) setStep((s) => Math.min(s + 1, 3));
  }, [step, validateStep]);

  const handleBack = useCallback(() => {
    setStep((s) => Math.max(s - 1, 1));
  }, []);

  const isPending = isDraftSaving || isUploadingImages;

  return (
    <FormProvider {...methods}>
      <div className="mx-auto max-w-4xl">
        {/* Stepper */}
        <nav className="mb-8" aria-label="Прогресс">
          <ol className="flex items-center gap-2">
            {STEPS.map((s, i) => (
              <li key={s.id} className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => {
                    if (s.id < step) setStep(s.id);
                  }}
                  className={cn(
                    'flex items-center gap-2 rounded-full px-3 py-1.5 text-sm font-medium transition-colors',
                    step === s.id
                      ? 'bg-primary text-primary-foreground'
                      : step > s.id
                        ? 'bg-emerald-600/20 text-emerald-400 cursor-pointer'
                        : 'bg-muted text-muted-foreground',
                  )}
                  aria-current={step === s.id ? 'step' : undefined}
                >
                  <span
                    className={cn(
                      'flex h-5 w-5 items-center justify-center rounded-full text-xs',
                      step === s.id
                        ? 'bg-primary-foreground/20'
                        : step > s.id
                          ? 'bg-emerald-600/30'
                          : 'bg-muted-foreground/20',
                    )}
                  >
                    {step > s.id ? '✓' : s.id}
                  </span>
                  <span className="hidden sm:inline">{s.label}</span>
                </button>
                {i < STEPS.length - 1 && (
                  <div
                    className={cn(
                      'h-px w-6 sm:w-10',
                      step > s.id ? 'bg-emerald-600/40' : 'bg-border',
                    )}
                  />
                )}
              </li>
            ))}
          </ol>
        </nav>

        <form onSubmit={handleSubmit(handleSubmitFinal)} noValidate>
          {/* Step 1: Основное */}
          {step === 1 && (
            <div className="space-y-6">
              <h2 className="text-xl font-semibold">Основная информация</h2>

              <div className="space-y-1.5">
                <label htmlFor="title" className="text-sm font-medium leading-none">
                  Название события
                </label>
                <input
                  id="title"
                  type="text"
                  placeholder="Новогодний вечер 2026"
                  className="flex h-10 w-full rounded-md border border-border bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                  {...methods.register('title')}
                  aria-invalid={!!methods.formState.errors.title}
                />
                {methods.formState.errors.title?.message && (
                  <p className="text-sm text-red-400">
                    {methods.formState.errors.title.message}
                  </p>
                )}
              </div>

              <div className="space-y-1.5">
                <label htmlFor="slug" className="text-sm font-medium leading-none">
                  Slug (URL)
                </label>
                <div className="flex items-center gap-2">
                  <input
                    id="slug"
                    type="text"
                    placeholder="new-year-2026"
                    className="flex h-10 flex-1 rounded-md border border-border bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                    value={slug}
                    onChange={handleSlugChange}
                    aria-invalid={!!methods.formState.errors.slug}
                  />
                  <span className="shrink-0 text-sm text-muted-foreground">
                    {organization?.slug ?? 'org'}.tdpay.ru/events/
                    <span className="text-primary">{slug || '...'}</span>
                  </span>
                </div>
                {methods.formState.errors.slug?.message && (
                  <p className="text-sm text-red-400">
                    {methods.formState.errors.slug.message}
                  </p>
                )}
              </div>

              <div className="space-y-1.5">
                <label htmlFor="description_md" className="text-sm font-medium leading-none">
                  Описание{' '}
                  <span className="text-muted-foreground">(Markdown)</span>
                </label>
                <textarea
                  id="description_md"
                  rows={5}
                  placeholder="Опишите событие... Поддерживается **жирный**, *курсив*"
                  className="flex min-h-[120px] w-full rounded-md border border-border bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                  {...methods.register('description_md')}
                />
                <p className="text-xs text-muted-foreground">
                  Поддерживается Markdown: **жирный**, *курсив*, [ссылка](url)
                </p>
              </div>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <label htmlFor="location_name" className="text-sm font-medium leading-none">
                    Место проведения
                  </label>
                  <input
                    id="location_name"
                    type="text"
                    placeholder="Ресторан «Чайка»"
                    className="flex h-10 w-full rounded-md border border-border bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                    {...methods.register('location_name')}
                    aria-invalid={!!methods.formState.errors.location_name}
                  />
                  {methods.formState.errors.location_name?.message && (
                    <p className="text-sm text-red-400">
                      {methods.formState.errors.location_name.message}
                    </p>
                  )}
                </div>
                <div className="space-y-1.5">
                  <label htmlFor="location_address" className="text-sm font-medium leading-none">
                    Адрес{' '}
                    <span className="text-muted-foreground">(опционально)</span>
                  </label>
                  <input
                    id="location_address"
                    type="text"
                    placeholder="ул. Примерная, д. 1"
                    className="flex h-10 w-full rounded-md border border-border bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                    {...methods.register('location_address')}
                  />
                </div>
              </div>

              <div className="rounded-lg border border-border p-4 space-y-4">
                <h3 className="text-sm font-semibold">Расписание</h3>
                <ScheduleEditor />
              </div>

              <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
                <ImageUpload
                  label="Картинка карточки"
                  hint="Отображается в списке событий. WebP, PNG, JPEG до 5 МБ."
                  currentUrl={event?.image_card_url}
                  selectedFile={cardFile}
                  onFileChange={setCardFile}
                  isUploading={isUploadingImages}
                  data-testid="image-card-upload"
                />
                <ImageUpload
                  label="Фоновое изображение"
                  hint="Отображается на странице события. WebP, PNG, JPEG до 5 МБ."
                  currentUrl={event?.image_background_url}
                  selectedFile={bgFile}
                  onFileChange={setBgFile}
                  isUploading={isUploadingImages}
                  data-testid="image-bg-upload"
                />
              </div>
            </div>
          )}

          {/* Step 2: Тарифы */}
          {step === 2 && (
            <div className="space-y-6">
              <h2 className="text-xl font-semibold">Тарифы и вместимость</h2>
              <div className="rounded-lg border border-border p-4 space-y-4">
                <h3 className="text-sm font-semibold">Политика вместимости</h3>
                <CapacityPolicyEditor />
              </div>
              <div className="rounded-lg border border-border p-4">
                <TariffsEditor />
              </div>
            </div>
          )}

          {/* Step 3: Поля формы */}
          {step === 3 && (
            <div className="space-y-6">
              <h2 className="text-xl font-semibold">Поля формы покупателя</h2>
              <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_320px]">
                <div className="rounded-lg border border-border p-4">
                  <CustomFieldsEditor />
                </div>
                <div className="lg:sticky lg:top-4 lg:self-start">
                  <BookingFormPreview />
                </div>
              </div>
            </div>
          )}

          {/* Footer */}
          <div className="mt-8 flex flex-col-reverse gap-3 border-t border-border pt-6 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex gap-3">
              <Button
                type="button"
                variant="outline"
                onClick={saveDraft}
                disabled={isPending}
              >
                {isDraftSaving ? (
                  <>
                    <Spinner size="sm" /> Сохранение...
                  </>
                ) : (
                  'Сохранить черновик'
                )}
              </Button>
            </div>

            <div className="flex gap-3">
              {step > 1 && (
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleBack}
                  disabled={isPending}
                >
                  Назад
                </Button>
              )}

              {step < 3 ? (
                <Button type="button" onClick={handleNext} disabled={isPending}>
                  Далее
                </Button>
              ) : (
                <div className="flex gap-3">
                  <Button type="submit" disabled={isPending}>
                    {isPending ? (
                      <>
                        <Spinner size="sm" /> Сохранение...
                      </>
                    ) : isEdit ? (
                      'Сохранить'
                    ) : (
                      'Создать событие'
                    )}
                  </Button>
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={handleSubmitForModeration}
                    disabled={isPending}
                  >
                    {isPending ? (
                      <>
                        <Spinner size="sm" /> Отправка...
                      </>
                    ) : (
                      'Отправить на модерацию'
                    )}
                  </Button>
                </div>
              )}
            </div>
          </div>
        </form>
      </div>
    </FormProvider>
  );
}