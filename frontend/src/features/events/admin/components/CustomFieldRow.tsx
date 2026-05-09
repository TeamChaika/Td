'use client';

/**
 * CustomFieldRow — строка кастомного поля в редакторе.
 * Типы: text, textarea, number, select, multiselect, checkbox, date.
 */
import { useState, useEffect } from 'react';
import { useFormContext } from 'react-hook-form';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { Button } from '@/components/ui/button';
import type { EventWizardFormData } from '../schemas';

const FIELD_TYPES = [
  { value: 'text', label: 'Текст' },
  { value: 'textarea', label: 'Многострочный текст' },
  { value: 'number', label: 'Число' },
  { value: 'select', label: 'Выпадающий список' },
  { value: 'multiselect', label: 'Множественный выбор' },
  { value: 'checkbox', label: 'Чекбокс' },
  { value: 'date', label: 'Дата' },
] as const;

interface CustomFieldRowProps {
  index: number;
  onRemove: () => void;
  onMoveUp?: () => void;
  onMoveDown?: () => void;
  isFirst: boolean;
  isLast: boolean;
}

export function CustomFieldRow({
  index,
  onRemove,
  onMoveUp,
  onMoveDown,
  isFirst,
  isLast,
}: CustomFieldRowProps) {
  const {
    register,
    watch,
    setValue,
    formState: { errors },
  } = useFormContext<EventWizardFormData>();

  const fieldType = watch(`custom_fields.${index}.type`);
  const currentOptions = watch(`custom_fields.${index}.options`);
  const fieldErrors = (
    errors.custom_fields as unknown as
      | Array<Record<string, { message?: string } | undefined>>
      | undefined
  )?.[index];

  const [optionsStr, setOptionsStr] = useState(
    (currentOptions ?? []).join(', '),
  );

  useEffect(() => {
    const arr = optionsStr
      .split(',')
      .map((s: string) => s.trim())
      .filter(Boolean);
    setValue(`custom_fields.${index}.options`, arr, { shouldValidate: true });
  }, [optionsStr, index, setValue]);

  const showOptions =
    fieldType === 'select' || fieldType === 'multiselect';
  const showMaxLength = fieldType === 'text' || fieldType === 'textarea';

  return (
    <div className="rounded-lg border border-border p-4 space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">Поле {index + 1}</span>
        <div className="flex items-center gap-1">
          {onMoveUp && (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={onMoveUp}
              disabled={isFirst}
              aria-label="Переместить вверх"
            >
              ↑
            </Button>
          )}
          {onMoveDown && (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={onMoveDown}
              disabled={isLast}
              aria-label="Переместить вниз"
            >
              ↓
            </Button>
          )}
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-muted-foreground hover:text-red-400"
            onClick={onRemove}
            aria-label={`Удалить поле ${index + 1}`}
          >
            ×
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {/* ID */}
        <div className="space-y-1.5">
          <Label htmlFor={`custom_fields.${index}.id`}>ID (slug)</Label>
          <Input
            id={`custom_fields.${index}.id`}
            placeholder="dietary_requirements"
            {...register(`custom_fields.${index}.id`)}
            aria-invalid={!!fieldErrors?.id}
          />
          {fieldErrors?.id?.message && (
            <p className="text-sm text-red-400">{fieldErrors.id.message}</p>
          )}
        </div>

        {/* Label */}
        <div className="space-y-1.5">
          <Label htmlFor={`custom_fields.${index}.label`}>Название</Label>
          <Input
            id={`custom_fields.${index}.label`}
            placeholder="Диетические требования"
            {...register(`custom_fields.${index}.label`)}
            aria-invalid={!!fieldErrors?.label}
          />
          {fieldErrors?.label?.message && (
            <p className="text-sm text-red-400">{fieldErrors.label.message}</p>
          )}
        </div>

        {/* Type */}
        <div className="space-y-1.5">
          <Label htmlFor={`custom_fields.${index}.type`}>Тип</Label>
          <Select
            id={`custom_fields.${index}.type`}
            {...register(`custom_fields.${index}.type`)}
            aria-invalid={!!fieldErrors?.type}
          >
            {FIELD_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </Select>
          {fieldErrors?.type?.message && (
            <p className="text-sm text-red-400">{fieldErrors.type.message}</p>
          )}
        </div>

        {/* Required */}
        <div className="flex items-end">
          <Checkbox
            id={`custom_fields.${index}.required`}
            label="Обязательное"
            {...register(`custom_fields.${index}.required`)}
          />
        </div>
      </div>

      {/* Options for select/multiselect */}
      {showOptions && (
        <div className="space-y-1.5">
          <Label htmlFor={`custom_fields.${index}.options_str`}>
            Опции (через запятую)
          </Label>
          <Input
            id={`custom_fields.${index}.options_str`}
            placeholder="Вегетарианец, Веган, Без ограничений"
            value={optionsStr}
            onChange={(e) => setOptionsStr(e.target.value)}
          />
          {fieldErrors?.options?.message && (
            <p className="text-sm text-red-400">
              {fieldErrors.options.message}
            </p>
          )}
        </div>
      )}

      {/* Max length for text/textarea */}
      {showMaxLength && (
        <div className="space-y-1.5">
          <Label htmlFor={`custom_fields.${index}.max_length`}>
            Макс. длина символов{' '}
            <span className="text-muted-foreground">(опционально)</span>
          </Label>
          <Input
            id={`custom_fields.${index}.max_length`}
            type="number"
            min={1}
            max={10000}
            placeholder="500"
            {...register(`custom_fields.${index}.max_length`, {
              valueAsNumber: true,
            })}
          />
        </div>
      )}
    </div>
  );
}