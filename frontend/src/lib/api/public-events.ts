/**
 * Серверные fetch-функции для публичных эндпоинтов событий.
 * Используются в RSC с ISR (revalidate).
 *
 * Endpoints:
 *   GET /api/v1/public/events        — список published событий
 *   GET /api/v1/public/events/{slug} — детали события + активные тарифы
 */
import type {
  PublicEventDetail,
  PublicEventListItem,
  PaginatedResponse,
} from '@/types/api';

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

async function fetchFromApi<T>(
  path: string,
  tenantSlug: string,
  revalidate = 60,
): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    headers: { 'X-Tenant-Slug': tenantSlug },
    next: { revalidate },
  });

  if (!res.ok) {
    // 404 — валидный кейс (событие не найдено), не кидаем ошибку
    if (res.status === 404) {
      throw new NotFoundError(`Resource not found: ${path}`);
    }
    // 5xx / network error — пробрасываем для error boundary
    throw new Error(
      `API error: ${res.status} ${res.statusText} for ${path}`,
    );
  }

  return res.json() as Promise<T>;
}

class NotFoundError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'NotFoundError';
  }
}

/** Список опубликованных событий организации */
export async function fetchPublicEvents(
  tenantSlug: string,
  params?: { page?: number; per_page?: number; sort?: string },
): Promise<PaginatedResponse<PublicEventListItem>> {
  const page = params?.page ?? 1;
  const perPage = params?.per_page ?? 12;
  const sort = params?.sort ?? 'schedule.starts_at';

  return fetchFromApi<PaginatedResponse<PublicEventListItem>>(
    `/api/v1/public/events?page=${page}&per_page=${perPage}&sort=${encodeURIComponent(sort)}`,
    tenantSlug,
  );
}

/** Детали события по slug.
 *
 * Возвращает null если событие не найдено (404).
 * Пробрасывает ошибку при 5xx / network error.
 */
export async function fetchPublicEvent(
  tenantSlug: string,
  eventSlug: string,
): Promise<PublicEventDetail | null> {
  try {
    return await fetchFromApi<PublicEventDetail>(
      `/api/v1/public/events/${encodeURIComponent(eventSlug)}`,
      tenantSlug,
    );
  } catch (err) {
    if (err instanceof NotFoundError) {
      return null;
    }
    throw err;
  }
}