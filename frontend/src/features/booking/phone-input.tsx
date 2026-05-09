'use client';

/**
 * PhoneInput — поле ввода телефона с маской +7 (___) ___-__-__.
 * Реализовано без внешних библиотек масок.
 */
import { useRef } from 'react';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils/cn';

interface PhoneInputProps {
  value: string;
  onChange: (value: string) => void;
  error?: string;
  disabled?: boolean;
}

/** Форматирует строку цифр в маску +7 (___) ___-__-__ */
function formatPhone(digits: string): string {
  // Убираем всё кроме цифр, берём первые 11
  const d = digits.replace(/\D/g, '').slice(0, 11);
  if (d.length === 0) return '';

  // Если начинается с 8 или 7 — заменяем на 7
  const local = d.startsWith('8') || d.startsWith('7') ? d.slice(1) : d;
  const parts = local.slice(0, 10);

  let result = '+7';
  if (parts.length > 0) result += ` (${parts.slice(0, 3)}`;
  if (parts.length >= 3) result += `) ${parts.slice(3, 6)}`;
  if (parts.length >= 6) result += `-${parts.slice(6, 8)}`;
  if (parts.length >= 8) result += `-${parts.slice(8, 10)}`;
  return result;
}

export function PhoneInput({ value, onChange, error, disabled }: PhoneInputProps) {
  const ref = useRef<HTMLInputElement>(null);

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const raw = e.target.value;
    // Извлекаем только цифры
    const digits = raw.replace(/\D/g, '');
    const formatted = formatPhone(digits);
    onChange(formatted);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    // При Backspace в начале — не допускать удаления '+7'
    if (e.key === 'Backspace' && ref.current) {
      const pos = ref.current.selectionStart ?? 0;
      if (pos <= 2) {
        e.preventDefault();
      }
    }
  }

  return (
    <div>
      <Input
        ref={ref}
        type="tel"
        inputMode="numeric"
        placeholder="+7 (___) ___-__-__"
        value={value}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        className={cn(error && 'border-destructive focus-visible:ring-destructive')}
        aria-invalid={!!error}
      />
      {error && (
        <p className="mt-1 text-xs text-destructive">{error}</p>
      )}
    </div>
  );
}
