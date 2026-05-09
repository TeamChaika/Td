'use client';

/**
 * CapacityPolicyEditor — выбор политики вместимости.
 * Поля соответствуют backend Pydantic: total={limit}, hybrid={total}.
 */
import { useFormContext, type FieldError } from 'react-hook-form';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import type { EventWizardFormData } from '../schemas';

const POLICY_OPTIONS = [
  { value: 'unlimited', label: 'Без лимита' },
  { value: 'total', label: 'Общий лимит' },
  { value: 'per_tariff', label: 'Лимит на тариф' },
  { value: 'hybrid', label: 'Гибрид (общий + на тариф)' },
] as const;

function errMsg(err: FieldError | undefined): string | undefined {
  return err?.message;
}

export function CapacityPolicyEditor() {
  const {
    register,
    watch,
    formState: { errors },
  } = useFormContext<EventWizardFormData>();

  const policyType = watch('capacity_policy.type');
  const pErr = errors.capacity_policy as
    | Record<string, FieldError | undefined>
    | undefined;

  return (
    <div className="space-y-4">
      <div className="space-y-1.5">
        <Label htmlFor="capacity_policy.type">Политика вместимости</Label>
        <Select
          id="capacity_policy.type"
          {...register('capacity_policy.type')}
          aria-invalid={!!pErr?.type}
        >
          {POLICY_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </Select>
        {errMsg(pErr?.type) && (
          <p className="text-sm text-red-400">{errMsg(pErr?.type)}</p>
        )}
      </div>

      {policyType === 'total' && (
        <div className="space-y-1.5">
          <Label htmlFor="capacity_policy.limit">Общий лимит мест</Label>
          <Input
            id="capacity_policy.limit"
            type="number"
            min={1}
            placeholder="100"
            {...register('capacity_policy.limit', { valueAsNumber: true })}
            aria-invalid={!!pErr?.limit}
          />
          {errMsg(pErr?.limit) && (
            <p className="text-sm text-red-400">{errMsg(pErr?.limit)}</p>
          )}
        </div>
      )}

      {policyType === 'hybrid' && (
        <div className="space-y-1.5">
          <Label htmlFor="capacity_policy.total">Общий лимит мест</Label>
          <Input
            id="capacity_policy.total"
            type="number"
            min={1}
            placeholder="100"
            {...register('capacity_policy.total', { valueAsNumber: true })}
            aria-invalid={!!pErr?.total}
          />
          {errMsg(pErr?.total) && (
            <p className="text-sm text-red-400">{errMsg(pErr?.total)}</p>
          )}
        </div>
      )}

      {policyType === 'per_tariff' && (
        <p className="text-sm text-muted-foreground">
          Каждый тариф должен иметь свой лимит мест.
        </p>
      )}
      {policyType === 'hybrid' && (
        <p className="text-sm text-muted-foreground">
          Общий лимит + каждый тариф имеет свой лимит.
        </p>
      )}
    </div>
  );
}