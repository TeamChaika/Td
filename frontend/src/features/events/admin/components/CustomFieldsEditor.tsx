'use client';

/**
 * CustomFieldsEditor — редактор кастомных полей формы покупателя.
 * Максимум 10 полей. Add/Remove/Reorder.
 */
import { useCallback } from 'react';
import { useFormContext, useFieldArray } from 'react-hook-form';
import { Button } from '@/components/ui/button';
import { CustomFieldRow } from './CustomFieldRow';
import type { EventWizardFormData } from '../schemas';

export function CustomFieldsEditor() {
  const {
    control,
    formState: { errors },
  } = useFormContext<EventWizardFormData>();

  const { fields, append, remove, swap } = useFieldArray({
    control,
    name: 'custom_fields',
  });

  const addField = useCallback(() => {
    if (fields.length >= 10) return;
    append({
      id: '',
      label: '',
      type: 'text',
      required: false,
      options: [],
    });
  }, [append, fields.length]);

  const fieldsError = errors.custom_fields;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <span className="text-sm font-medium leading-none">
            Поля формы покупателя
          </span>
          <p className="mt-1 text-xs text-muted-foreground">
            Дополнительные поля, которые гость заполнит при бронировании.
            Максимум 10 полей.
          </p>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={addField}
          disabled={fields.length >= 10}
        >
          + Добавить поле
        </Button>
      </div>

      {fieldsError?.root && (
        <p className="text-sm text-red-400">{fieldsError.root.message}</p>
      )}
      {fieldsError?.message && typeof fieldsError.message === 'string' && (
        <p className="text-sm text-red-400">{fieldsError.message}</p>
      )}

      {fields.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border p-6 text-center">
          <p className="text-sm text-muted-foreground">
            Нет дополнительных полей. Добавьте поля, если нужно собрать
            дополнительную информацию от гостей (например, диетические
            предпочтения, возраст).
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {fields.map((field, index) => (
            <CustomFieldRow
              key={field.id}
              index={index}
              onRemove={() => remove(index)}
              onMoveUp={index > 0 ? () => swap(index, index - 1) : undefined}
              onMoveDown={
                index < fields.length - 1
                  ? () => swap(index, index + 1)
                  : undefined
              }
              isFirst={index === 0}
              isLast={index === fields.length - 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}