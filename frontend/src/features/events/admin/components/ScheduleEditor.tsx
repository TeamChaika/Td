'use client';

/**
 * ScheduleEditor — редактор расписания события.
 * Поддерживает 3 типа: single, sessions (с id), period.
 * ends_at — required во всех типах (backend Pydantic-контракт).
 */
import { useCallback } from 'react';
import { useFormContext, useFieldArray, type FieldError } from 'react-hook-form';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';
import type { EventWizardFormData } from '../schemas';
import { generateSessionId } from '../schemas';

const SCHEDULE_TYPES = [
  { value: 'single', label: 'Разовое событие' },
  { value: 'sessions', label: 'Несколько сеансов' },
  { value: 'period', label: 'Период (фестиваль)' },
] as const;

function errMsg(err: FieldError | undefined): string | undefined {
  return err?.message;
}

export function ScheduleEditor() {
  const {
    register,
    watch,
    control,
    formState: { errors },
  } = useFormContext<EventWizardFormData>();

  const scheduleType = watch('schedule.type');

  const { fields, append, remove } = useFieldArray({
    control,
    name: 'schedule.sessions',
  });

  const addSession = useCallback(() => {
    append({
      id: generateSessionId(),
      starts_at: '',
      ends_at: '',
    });
  }, [append]);

  const sErr = errors.schedule as
    | Record<string, FieldError | undefined>
    | undefined;

  return (
    <div className="space-y-4">
      <div className="space-y-1.5">
        <Label htmlFor="schedule.type">Тип расписания</Label>
        <Select
          id="schedule.type"
          {...register('schedule.type')}
          aria-invalid={!!sErr?.type}
        >
          {SCHEDULE_TYPES.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </Select>
        {errMsg(sErr?.type) && (
          <p className="text-sm text-red-400">{errMsg(sErr?.type)}</p>
        )}
      </div>

      {/* Single */}
      {scheduleType === 'single' && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="schedule.starts_at">Дата и время начала</Label>
            <Input
              id="schedule.starts_at"
              type="datetime-local"
              {...register('schedule.starts_at')}
              aria-invalid={!!sErr?.starts_at}
            />
            {errMsg(sErr?.starts_at) && (
              <p className="text-sm text-red-400">{errMsg(sErr?.starts_at)}</p>
            )}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="schedule.ends_at">Дата и время окончания</Label>
            <Input
              id="schedule.ends_at"
              type="datetime-local"
              {...register('schedule.ends_at')}
              aria-invalid={!!sErr?.ends_at}
            />
            {errMsg(sErr?.ends_at) && (
              <p className="text-sm text-red-400">{errMsg(sErr?.ends_at)}</p>
            )}
          </div>
        </div>
      )}

      {/* Sessions */}
      {scheduleType === 'sessions' && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <Label>Сеансы</Label>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={addSession}
            >
              + Добавить сеанс
            </Button>
          </div>
          {sErr?.sessions?.message &&
            typeof sErr.sessions.message === 'string' && (
              <p className="text-sm text-red-400">{sErr.sessions.message}</p>
            )}
          <div className="space-y-3">
            {fields.map((field, index) => {
              const sessionErrors = (
                sErr?.sessions as unknown as
                  | Array<Record<string, FieldError | undefined>>
                  | undefined
              )?.[index];
              return (
                <div
                  key={field.id}
                  className="flex flex-col gap-2 rounded-lg border border-border p-3 sm:flex-row sm:items-start"
                >
                  <input
                    type="hidden"
                    {...register(`schedule.sessions.${index}.id`)}
                  />
                  <div className="flex-1 space-y-1.5">
                    <Label
                      htmlFor={`schedule.sessions.${index}.starts_at`}
                      className="text-xs"
                    >
                      Начало
                    </Label>
                    <Input
                      id={`schedule.sessions.${index}.starts_at`}
                      type="datetime-local"
                      {...register(`schedule.sessions.${index}.starts_at`)}
                      aria-invalid={!!sessionErrors?.starts_at}
                    />
                    {errMsg(sessionErrors?.starts_at) && (
                      <p className="text-sm text-red-400">
                        {errMsg(sessionErrors?.starts_at)}
                      </p>
                    )}
                  </div>
                  <div className="flex-1 space-y-1.5">
                    <Label
                      htmlFor={`schedule.sessions.${index}.ends_at`}
                      className="text-xs"
                    >
                      Окончание
                    </Label>
                    <Input
                      id={`schedule.sessions.${index}.ends_at`}
                      type="datetime-local"
                      {...register(`schedule.sessions.${index}.ends_at`)}
                      aria-invalid={!!sessionErrors?.ends_at}
                    />
                    {errMsg(sessionErrors?.ends_at) && (
                      <p className="text-sm text-red-400">
                        {errMsg(sessionErrors?.ends_at)}
                      </p>
                    )}
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="mt-5 shrink-0 text-muted-foreground hover:text-red-400"
                    onClick={() => remove(index)}
                    aria-label={`Удалить сеанс ${index + 1}`}
                  >
                    ×
                  </Button>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Period */}
      {scheduleType === 'period' && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="schedule.starts_at">Дата начала</Label>
              <Input
                id="schedule.starts_at"
                type="datetime-local"
                {...register('schedule.starts_at')}
                aria-invalid={!!sErr?.starts_at}
              />
              {errMsg(sErr?.starts_at) && (
                <p className="text-sm text-red-400">{errMsg(sErr?.starts_at)}</p>
              )}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="schedule.ends_at">Дата окончания</Label>
              <Input
                id="schedule.ends_at"
                type="datetime-local"
                {...register('schedule.ends_at')}
                aria-invalid={!!sErr?.ends_at}
              />
              {errMsg(sErr?.ends_at) && (
                <p className="text-sm text-red-400">{errMsg(sErr?.ends_at)}</p>
              )}
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="schedule.description">
              Описание расписания{' '}
              <span className="text-muted-foreground">(опционально)</span>
            </Label>
            <Textarea
              id="schedule.description"
              rows={3}
              placeholder="Например: «Ежедневно с 10:00 до 22:00, кроме понедельника»"
              {...register('schedule.description')}
            />
          </div>
        </div>
      )}
    </div>
  );
}