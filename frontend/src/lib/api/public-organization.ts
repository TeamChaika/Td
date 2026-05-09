/**
 * Данные организации для статических страниц витрины.
 *
 * Брендинг (brand_name, logo_url, brand_color) берётся из TenantContext
 * (получен через GET /api/v1/public/tenant/resolve).
 *
 * Контактные данные и политики (contact_email, contact_phone, refund_policy,
 * about_text, privacy_policy) пока НЕ доступны через публичный API.
 * Нужен новый эндпоинт — см. финальный отчёт, секция «Что нужно от backend».
 */
import type { TenantContext } from '@/features/events/public';

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export interface OrganizationPublicInfo {
  aboutText: string | null;
  contactEmail: string | null;
  contactPhone: string | null;
  contactAddress: string | null;
  refundPolicy: string | null;
  privacyPolicy: string | null;
}

/**
 * Получить публичную информацию об организации.
 *
 * Делает запрос к GET /api/v1/public/tenant/resolve для получения
 * contact_email, contact_phone, refund_policy (если бэкенд начнёт их
 * возвращать — сейчас PublicTenantResolveResponse их не содержит).
 *
 * Поля about_text, contact_address, privacy_policy отсутствуют
 * в модели Organization — требуют добавления на backend.
 */
export async function fetchPublicOrganization(
  tenant: TenantContext,
): Promise<OrganizationPublicInfo> {
  try {
    const url = `${API_BASE}/api/v1/public/tenant/resolve?slug=${encodeURIComponent(tenant.slug)}`;
    const res = await fetch(url, {
      headers: { 'X-Tenant-Slug': tenant.slug },
      next: { revalidate: 3600 },
    });

    if (!res.ok) {
      return emptyInfo();
    }

    // eslint-disable-next-line @typescript-eslint/no-unsafe-assignment
    const data = await res.json();
    const d = data as Record<string, unknown>;

    return {
      aboutText: null,
      contactEmail: typeof d.contact_email === 'string' ? d.contact_email : null,
      contactPhone: typeof d.contact_phone === 'string' ? d.contact_phone : null,
      contactAddress: null,
      refundPolicy: typeof d.refund_policy === 'string' ? d.refund_policy : null,
      privacyPolicy: null,
    };
  } catch {
    return emptyInfo();
  }
}

function emptyInfo(): OrganizationPublicInfo {
  return {
    aboutText: null,
    contactEmail: null,
    contactPhone: null,
    contactAddress: null,
    refundPolicy: null,
    privacyPolicy: null,
  };
}