'use client';

/**
 * TariffRow — строка тарифа в редакторе.
 * Inline редактирование: name, description, price (в рублях), capacity_limit, is_active.
 */
import { useFormContext, useWatch } from 'react-hook-form';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Checkbox } from '@/components/ui/checkbox';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils/cn';
import type { EventWizardFormData } from '../schemas';

interface TariffRowProps {
  index: number;
  onRemove: () => void;
  onMoveUp?: () => void;
  onMoveDown?: () => void;
  isFirst: boolean;
  isLast: boolean;
  totalTariffs: number;
}

export function TariffRow({
  index,
  onRemove,
  onMoveUp,
  onMoveDown,
  isFirst,
  isLast,
  totalTariffs,
}: TariffRowProps) {
  const {
    register,
    formState: { errors },
  } = useFormContext<EventWizardFormData>();

  const capacityPolicyType = useWatch({ name: 'capacity_policy.type' });
  const showCapacityLimit =
    capacityPolicyType === 'per_tariff' || capacityPolicyType === 'hybrid';

  const tariffErrors = (
    errors.tariffs as unknown as
      | Array<Record<string, { message?: string } | undefined>>
      | undefined
  )?.[index];

  return (
    <div className="rounded-lg border border-border p-4 space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">Тариф {index + 1}</span>
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
          {totalTariffs > 1 && (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-7 w-7 text-muted-foreground hover:text-red-400"
              onClick={onRemove}
              aria-label={`Удалить тариф ${index + 1}`}
            >
              ×
            </Button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {/* Name */}
        <div className="space-y-1.5 sm:col-span-2">
          <Label htmlFor={`tariffs.${index}.name`}>Название</Label>
          <Input
            id={`tariffs.${index}.name`}
            placeholder="Например: «Стандарт», «VIP»"
            {...register(`tariffs.${index}.name`)}
            aria-invalid={!!tariffErrors?.name}
          />
          {tariffErrors?.name && (
            <p className="text-sm text-red-400">{tariffErrors.name.message}</p>
          )}
        </div>

        {/* Description */}
        <div className="space-y-1.5 sm:col-span-2">
          <Label htmlFor={`tariffs.${index}.description`}>
            Описание{' '}
            <span className="text-muted-foreground">(опционально)</span>
          </Label>
          <Textarea
            id={`tariffs.${index}.description`}
            rows={2}
            placeholder="Что входит в тариф..."
            {...register(`tariffs.${index}.description`)}
          />
        </div>

        {/* Price */}
        <div className="space-y-1.5">
          <Label htmlFor={`tariffs.${index}.price_rub`}>Цена, ₽</Label>
          <Input
            id={`tariffs.${index}.price_rub`}
            type="number"
            min={0}
            step="0.01"
            placeholder="1500"
            {...register(`tariffs.${index}.price_rub`, { valueAsNumber: true })}
            aria-invalid={!!tariffErrors?.price_rub}
          />
          {tariffErrors?.price_rub && (
            <p className="text-sm text-red-400">
              {tariffErrors.price_rub.message}
            </p>
          )}
        </div>

        {/* Capacity limit */}
        {showCapacityLimit && (
          <div className="space-y-1.5">
            <Label htmlFor={`tariffs.${index}.capacity_limit`}>
              Лимит мест
            </Label>
            <Input
              id={`tariffs.${index}.capacity_limit`}
              type="number"
              min={1}
              placeholder="50"
              {...register(`tariffs.${index}.capacity_limit`, {
                valueAsNumber: true,
              })}
              aria-invalid={!!tariffErrors?.capacity_limit}
            />
            {tariffErrors?.capacity_limit && (
              <p className="text-sm text-red-400">
                {tariffErrors.capacity_limit.message}
              </p>
            )}
          </div>
        )}

        {/* is_active */}
        <div className={cn('flex items-end', !showCapacityLimit && 'sm:col-span-1')}>
          <Checkbox
            id={`tariffs.${index}.is_active`}
            label="Активен"
            {...register(`tariffs.${index}.is_active`)}
          />
        </div>
      </div>
    </div>
  );
}