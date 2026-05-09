/**
 * HTTP-клиент к TD Pay API.
 *
 * - Автоматически передаёт Authorization: Bearer <access_token> (из памяти)
 * - Добавляет X-Tenant-Slug из tenant-контекста для публичных роутов
 * - На 401 — пробует POST /api/v1/auth/refresh через httpOnly cookie → retry один раз
 *   Если и refresh 401 — вызывает logout + redirect
 * - Единая обработка ошибок через ApiError
 */
import { ofetch, type FetchContext, type FetchOptions, type FetchResponse } from 'ofetch';

import { getAccessToken, clearSession, setAccessToken } from '@/lib/auth/session-store';
import { ApiError } from './errors';

const baseURL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

/** Определить slug арендатора на клиенте (поддомен). */
function detectTenantSlugOnClient(): string | null {
  if (typeof window === 'undefined') return null;
  const platformDomain =
    process.env.NEXT_PUBLIC_PLATFORM_DOMAIN ?? 'tdpay.ru';
  const hostname = window.location.hostname;

  if (hostname === platformDomain || hostname === `www.${platformDomain}`) {
    return null;
  }
  const suffix = `.${platformDomain}`;
  if (hostname.endsWith(suffix)) {
    const slug = hostname.slice(0, -suffix.length);
    if (slug && !slug.includes('.')) return slug;
  }
  if (hostname.endsWith('.localhost')) {
    const slug = hostname.slice(0, -'.localhost'.length);
    if (slug && !slug.includes('.')) return slug;
  }
  return null;
}

/** Пытается обновить токен через httpOnly cookie. */
async function tryRefresh(): Promise<string | null> {
  try {
    const res = await ofetch<{ access_token: string; token_type: string }>(
      '/api/v1/auth/refresh',
      {
        baseURL,
        method: 'POST',
        credentials: 'include',
        retry: 0,
      },
    );
    return res.access_token;
  } catch {
    return null;
  }
}

/** Перенаправляет на страницу логина.
 *
 * Редиректит только если текущий путь — защищённый (/admin или /platform).
 * На публичных страницах (/register, /, etc.) просто молча очищает сессию —
 * иначе пользователь на /register вылетал бы на /admin/login при истёкшей куке.
 *
 * Добавляет ?reason=session_expired — страница логина может показать тост.
 */
function redirectToLogin(): void {
  if (typeof window === 'undefined') return;
  const path = window.location.pathname;
  if (path.startsWith('/platform')) {
    window.location.href = '/platform/login?reason=session_expired';
  } else if (path.startsWith('/admin')) {
    window.location.href = '/admin/login?reason=session_expired';
  }
  // На публичных страницах не редиректим — сессия уже очищена в api()
}

let refreshPromise: Promise<string | null> | null = null;

/** Скоординированный refresh: пока один запрос идёт, остальные ждут его результат. */
async function refreshTokenOnce(): Promise<string | null> {
  if (refreshPromise) return refreshPromise;
  refreshPromise = tryRefresh().finally(() => {
    refreshPromise = null;
  });
  return refreshPromise;
}

// Базовый клиент without retry логики
const rawApi = ofetch.create({
  baseURL,
  credentials: 'include',
  retry: 0,
  onRequest({ options }: FetchContext) {
    const token = getAccessToken();
    if (token) {
      const headers = new Headers(options.headers);
      headers.set('Authorization', `Bearer ${token}`);
      options.headers = headers;
    }

    if (!token) {
      const slug = detectTenantSlugOnClient();
      if (slug) {
        const headers = new Headers(options.headers);
        headers.set('X-Tenant-Slug', slug);
        options.headers = headers;
      }
    }
  },
  async onResponseError({ response }: FetchContext & { response: FetchResponse<unknown> }) {
    if (response) {
      throw await ApiError.fromResponse(response);
    }
  },
});

/**
 * API-клиент с автоматическим refresh-токеном.
 * При получении 401 пытается обновить токен и повторяет запрос.
 *
 * Использование:
 *   api<ResponseType>('/path')
 *   api<ResponseType>('/path', { method: 'POST', body: {...} })
 */
export async function api<T = unknown>(
  path: string,
  options?: FetchOptions<'json'>,
): Promise<T> {
  try {
    return await rawApi<T>(path, options);
  } catch (err) {
    if (!(err instanceof ApiError) || err.status !== 401) {
      throw err;
    }

    const newToken = await refreshTokenOnce();
    if (!newToken) {
      clearSession();
      redirectToLogin();
      throw new ApiError(401, {
        code: 'unauthorized',
        message: 'Сессия истекла. Пожалуйста, войдите снова.',
      });
    }

    setAccessToken(newToken);
    return rawApi<T>(path, options);
  }
}

/** Ручной запрос с произвольным tenant slug (для серверных компонентов). */
export async function apiWithTenant<T = unknown>(
  path: string,
  options: (FetchOptions<'json'> & { tenantSlug?: string | null }) = {},
): Promise<T> {
  const { tenantSlug, headers, ...rest } = options;
  const hdrs = new Headers(headers);
  if (tenantSlug) hdrs.set('X-Tenant-Slug', tenantSlug);
  return api<T>(path, { ...rest, headers: hdrs });
}