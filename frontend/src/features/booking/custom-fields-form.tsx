'use client';

/**
 * CustomFieldsForm — динамический рендерер кастомных полей события.
 * Поля описаны в event.custom_fields_schema (JSON Schema-like массив).
 */
import type { Control, FieldErrors, FieldValues, Path } from 'react-hook-form';
import { Controller } from 'react-hook-form';

import type { CustomField } from '@/types/api';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { cn } from '@/lib/utils/cn';

interface CustomFieldsFormProps<T extends FieldValues> {
  fields: CustomField[];
  control: Control<T>;
  errors: FieldErrors<T>;
  /** Префикс пути в форме, например "custom_fields" */
  fieldPath?: string;
}

export function CustomFieldsForm<T extends FieldValues>({
  fields,
  control,
  errors,
  fieldPath = 'custom_fields',
}: CustomFieldsFormProps<T>) {
  if (!fields || fields.length === 0) return null;

  return (
    <div className="space-y-4">
      {fields.map((field) => {
        const name = `${fieldPath}.${field.id}` as Path<T>;
        // Получаем ошибку по вложенному пути
        const parts = [`${fieldPath}`, field.id];
        let errNode: unknown = errors;
        for (const p of parts) {
          if (errNode && typeof errNode === 'object') {
            errNode = (errNode as Record<string, unknown>)[p];
          } else {
            errNode = undefined;
          }
        }
        const errorMessage =
          errNode && typeof errNode === 'object' && 'message' in errNode
            ? String((errNode as { message: unknown }).message)
            : undefined;

        return (
          <div key={field.id} className="space-y-1.5">
            <Label
              htmlFor={name}
              className={cn(
                field.required &&
                  "after:content-['*'] after:text-destructive after:ml-0.5",
              )}
            >
              {field.label}
            </Label>

            <Controller
              control={control}
              name={name}
              rules={{
                required: field.required ? `${field.label} обязательно` : false,
              }}
              render={({ field: f }) => {
                switch (field.type) {
                  case 'textarea':
                    return (
                      <Textarea
                        id={name}
                        placeholder={field.label}
                        maxLength={field.max_length}
                        value={String(f.value ?? '')}
                        onChange={f.onChange}
                        onBlur={f.onBlur}
                        className={cn(errorMessage && 'border-destructive')}
                        aria-invalid={!!errorMessage}
                      />
                    );

                  case 'number':
                    return (
                      <Input
                        id={name}
                        type="number"
                        placeholder={field.label}
                        value={f.value ?? ''}
                        onChange={(e) => f.onChange(e.target.valueAsNumber)}
                        onBlur={f.onBlur}
                        className={cn(errorMessage && 'border-destructive')}
                        aria-invalid={!!errorMessage}
                      />
                    );

                  case 'select':
                    return (
                      <Select
                        id={name}
                        value={String(f.value ?? '')}
                        onChange={(e) => f.onChange(e.target.value)}
                        onBlur={f.onBlur}
                        className={cn(errorMessage && 'border-destructive')}
                        aria-invalid={!!errorMessage}
                      >
                        <option value="">Выберите...</option>
                        {field.options?.map((opt) => (
                          <option key={opt} value={opt}>
                            {opt}
                          </option>
                        ))}
                      </Select>
                    );

                  case 'multiselect': {
                    const selected: string[] = Array.isArray(f.value) ? f.value : [];
                    return (
                      <div className="space-y-1.5">
                        {field.options?.map((opt) => (
                          <label
                            key={opt}
                            className="flex items-center gap-2 cursor-pointer text-sm"
                          >
                            <input
                              type="checkbox"
                              className="h-4 w-4 rounded border-border accent-primary"
                              checked={selected.includes(opt)}
                              onChange={(e) => {
                                if (e.target.checked) {
                                  f.onChange([...selected, opt]);
                                } else {
                                  f.onChange(selected.filter((v) => v !== opt));
                                }
                              }}
                            />
                            {opt}
                          </label>
                        ))}
                      </div>
                    );
                  }

                  case 'checkbox':
                    return (
                      <label className="flex items-center gap-2 cursor-pointer text-sm">
                        <input
                          id={name}
                          type="checkbox"
                          className="h-4 w-4 rounded border-border accent-primary"
                          checked={Boolean(f.value)}
                          onChange={(e) => f.onChange(e.target.checked)}
                          onBlur={f.onBlur}
                        />
                        {field.label}
                      </label>
                    );

                  case 'date':
                    return (
                      <Input
                        id={name}
                        type="date"
                        value={String(f.value ?? '')}
                        onChange={f.onChange}
                        onBlur={f.onBlur}
                        className={cn(errorMessage && 'border-destructive')}
                        aria-invalid={!!errorMessage}
                      />
                    );

                  default:
                    // text и прочие
                    return (
                      <Input
                        id={name}
                        type="text"
                        placeholder={field.label}
                        maxLength={field.max_length}
                        value={String(f.value ?? '')}
                        onChange={f.onChange}
                        onBlur={f.onBlur}
                        className={cn(errorMessage && 'border-destructive')}
                        aria-invalid={!!errorMessage}
                      />
                    );
                }
              }}
            />

            {errorMessage && (
              <p className="text-xs text-destructive">{errorMessage}</p>
            )}
          </div>
        );
      })}
    </div>
  );
}
