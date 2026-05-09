/**
 * Layout для всех страниц витрины арендатора внутри группы (tenant).
 * Резолвит tenant по subdomain и применяет брендинг.
 *
 * Страницы внутри этой группы:
 * - /events/[slug] — детали события
 * - /about, /contacts, /terms, /privacy — статические страницы
 *
 * Каталог (/) рендерится из root page.tsx с явным использованием TenantLayout.
 */
import { getCurrentTenantSlug, resolveTenant } from '@/lib/tenant/resolve';
import { TenantLayout } from '@/features/events/public';

export default async function TenantGroupLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const slug = await getCurrentTenantSlug();

  if (!slug) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-muted-foreground">Организация не найдена</p>
      </div>
    );
  }

  const tenant = await resolveTenant(slug);

  if (!tenant) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-muted-foreground">Организация не найдена</p>
      </div>
    );
  }

  return <TenantLayout tenant={tenant}>{children}</TenantLayout>;
}