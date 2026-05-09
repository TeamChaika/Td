/**
 * Форматирование денежных сумм.
 * Внутри системы суммы хранятся в копейках (integer) — форматтер принимает
 * именно копейки и возвращает строку вида `1 500 ₽`.
 */

const RUBLE_FORMATTER = new Intl.NumberFormat('ru-RU', {
  style: 'currency',
  currency: 'RUB',
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
});

/** Превратить копейки в строку `1 500 ₽`. */
export function formatKopecks(kopecks: number): string {
  const rubles = kopecks / 100;
  return RUBLE_FORMATTER.format(rubles);
}

/** Превратить копейки в строку без символа валюты (`1 500`). */
export function formatKopecksPlain(kopecks: number): string {
  const rubles = kopecks / 100;
  return new Intl.NumberFormat('ru-RU', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(rubles);
}

/** Распарсить строку «1500» / «1500,50» / «1 500,50» в копейки (integer). */
export function parseRublesToKopecks(value: string): number | null {
  const normalized = value.replace(/\s/g, '').replace(',', '.');
  const rubles = Number(normalized);
  if (!Number.isFinite(rubles) || rubles < 0) {
    return null;
  }
  return Math.round(rubles * 100);
}
