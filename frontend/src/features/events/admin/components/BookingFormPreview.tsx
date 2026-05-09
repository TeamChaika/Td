'use client';

/**
 * BookingFormPreview — превью формы бронирования для гостя.
 * Показывает, как будут выглядеть кастомные поля на витрине.
 * Типы: text, textarea, number, select, multiselect, checkbox, date.
 */
import { useWatch, useFormContext } from 'react-hook-form';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import type { EventWizardFormData, CustomFieldFormData } from '../schemas';

function PreviewField({ field }: { field: CustomFieldFormData }) {
  const id = `preview_${field.id}`;
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>
        {field.label}
        {field.required && <span className="ml-1 text-red-400">*</span>}
      </Label>
      {field.type === 'select' || field.type === 'multiselect' ? (
        <Select id={id} disabled>
          <option value="">Выберите...</option>
          {field.options?.map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </Select>
      ) : field.type === 'checkbox' ? (
        <Checkbox id={id} label={field.label} disabled />
      ) : field.type === 'textarea' ? (
        <textarea
          id={id}
          className="flex min-h-[80px] w-full rounded-md border border-border bg-background px-3 py-2 text-sm opacity-50"
          disabled
          rows={3}
        />
      ) : field.type === 'date' ? (
        <Input id={id} type="date" disabled />
      ) : field.type === 'number' ? (
        <Input id={id} type="number" placeholder="0" disabled />
      ) : (
        <Input id={id} type="text" placeholder="Введите значение" disabled />
      )}
    </div>
  );
}

export function BookingFormPreview() {
  const { control } = useFormContext<EventWizardFormData>();
  const customFields: CustomFieldFormData[] =
    useWatch({ control, name: 'custom_fields' }) ?? [];

  return (
    <div className="rounded-lg border border-border bg-card p-5">
      <h3 className="text-sm font-semibold mb-4">
        Предпросмотр формы для гостя
      </h3>

      {/* Стандартные поля */}
      <div className="space-y-3 mb-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="preview_first_name">
              Имя <span className="text-red-400">*</span>
            </Label>
            <Input id="preview_first_name" placeholder="Иван" disabled />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="preview_last_name">
              Фамилия <span className="text-red-400">*</span>
            </Label>
            <Input id="preview_last_name" placeholder="Иванов" disabled />
          </div>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="preview_email">
            Email <span className="text-red-400">*</span>
          </Label>
          <Input
            id="preview_email"
            type="email"
            placeholder="email@example.com"
            disabled
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="preview_phone">
            Телефон <span className="text-red-400">*</span>
          </Label>
          <Input
            id="preview_phone"
            type="tel"
            placeholder="+7 999 123-45-67"
            disabled
          />
        </div>
      </div>

      {customFields.length > 0 && (
        <div className="border-t border-border pt-4 space-y-3">
          <p className="text-xs text-muted-foreground">
            Дополнительные поля
          </p>
          {customFields.map((field) => (
            <PreviewField key={field.id} field={field} />
          ))}
        </div>
      )}

      {customFields.length === 0 && (
        <p className="text-xs text-muted-foreground italic">
          Дополнительные поля не добавлены. Гость увидит только стандартную
          форму (имя, фамилия, email, телефон).
        </p>
      )}
    </div>
  );
}