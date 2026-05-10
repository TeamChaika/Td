/**
 * Серверное разрешение текущего tenant'а (из subdomain).
 * Использовать в server-компонентах и Route Handlers.
 */
import { headers } from 'next/headers';

import type { TenantResolveResponse } from '@/types/api';

export interface TenantContext {
  slug: string;
  name: string;
  brandName: string | null;
  brandColor: string | null;
  logoUrl: string | null;
  status: string;
}

/** Получить slug из заголовка (выставляется middleware). */
export async function getCurrentTenantSlug(): Promise<string | null> {
  const hdrs = await headers();
  return hdrs.get('x-tenant-slug');
}

/**
 * Резолв полного контекста организации через API.
 */
export async function resolveTenant(
  slug: string,
): Promise<TenantContext | null> {
  if (!slug) return null;

  const baseURL = process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

  try {
    const res = await fetch(
      `${baseURL}/api/v1/public/tenant/resolve?slug=${encodeURIComponent(slug)}`,
      {
        headers: { 'X-Tenant-Slug': slug },
        next: { revalidate: 60 },
      },
    );

    if (!res.ok) return null;

    const data: TenantResolveResponse = await res.json();
    return {
      slug: data.slug,
      name: data.name,
      brandName: data.brand_name,
      brandColor: data.brand_color,
      logoUrl: data.logo_url,
      status: data.status,
    };
  } catch {
    return null;
  }
}