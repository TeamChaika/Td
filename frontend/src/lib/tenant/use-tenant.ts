'use client';

/**
 * useTenant — хук для публичной части.
 * Читает slug из subdomain и резолвит через /api/v1/public/tenant/resolve.
 */
import { useQuery } from '@tanstack/react-query';

import { api } from '@/lib/api/client';
import type { TenantResolveResponse } from '@/types/api';

function detectTenantSlug(): string | null {
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

/** Хук только для получения slug (без запроса к API). */
export function useTenantSlug(): string | null {
  if (typeof window === 'undefined') return null;
  return detectTenantSlug();
}

export function useTenant() {
  const slug = detectTenantSlug();

  return useQuery({
    queryKey: ['tenant', slug],
    queryFn: async () => {
      if (!slug) return null;
      return api<TenantResolveResponse>(
        `/api/v1/public/tenant/resolve?slug=${encodeURIComponent(slug)}`,
        {
          headers: { 'X-Tenant-Slug': slug },
        },
      );
    },
    enabled: !!slug,
    staleTime: 5 * 60 * 1000,
  });
}