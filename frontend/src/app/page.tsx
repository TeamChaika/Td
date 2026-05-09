/**
 * Главная страница приложения.
 * В зависимости от того, пришёл ли запрос на корневой домен (tdpay.ru)
 * или на поддомен (acme.tdpay.ru) — рендерим лендинг или витрину.
 *
 * Middleware выставляет заголовок `x-tenant-slug` для поддоменов.
 */
import { getCurrentTenantSlug, resolveTenant } from '@/lib/tenant/resolve';

import { LandingPage } from './_landing';
import { TenantCatalogPage } from './_tenant-catalog';

export default async function RootPage() {
  const slug = await getCurrentTenantSlug();
  if (slug) {
    const tenant = await resolveTenant(slug);
    if (tenant) return <TenantCatalogPage tenant={tenant} />;
  }
  return <LandingPage />;
}