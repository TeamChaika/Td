'use client';

/**
 * TariffsEditor — редактор списка тарифов.
 * Минимум 1 тариф. Inline add/remove/reorder.
 */
import { useCallback } from 'react';
import { useFormContext, useFieldArray } from 'react-hook-form';
import { Button } from '@/components/ui/button';
import { TariffRow } from './TariffRow';
import type { EventWizardFormData } from '../schemas';

export function TariffsEditor() {
  const {
    control,
    formState: { errors },
  } = useFormContext<EventWizardFormData>();

  const { fields, append, remove, swap } = useFieldArray({
    control,
    name: 'tariffs',
  });

  const addTariff = useCallback(() => {
    append({
      name: '',
      description: '',
      price_rub: 0,
      capacity_limit: null,
      is_active: true,
      sort_order: fields.length,
    });
  }, [append, fields.length]);

  const tariffsError = errors.tariffs;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium leading-none">Тарифы</span>
        <Button type="button" variant="outline" size="sm" onClick={addTariff}>
          + Добавить тариф
        </Button>
      </div>

      {tariffsError?.root && (
        <p className="text-sm text-red-400">{tariffsError.root.message}</p>
      )}
      {tariffsError?.message && typeof tariffsError.message === 'string' && (
        <p className="text-sm text-red-400">{tariffsError.message}</p>
      )}

      <div className="space-y-3">
        {fields.map((field, index) => (
          <TariffRow
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
            totalTariffs={fields.length}
          />
        ))}
      </div>
    </div>
  );
}