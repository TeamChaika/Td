/**
 * Утилита объединения Tailwind-классов с учётом конфликтов.
 * Использовать везде, где строятся динамические className.
 */
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
