/**
 * Страница «О нас» — /about
 */
import type { Metadata } from 'next';

import { getCurrentTenantSlug, resolveTenant } from '@/lib/tenant/resolve';
import { fetchPublicOrganization } from '@/lib/api/public-organization';
import { MarkdownContent } from '@/features/events/public';

export async function generateMetadata(): Promise<Metadata> {
  const slug = await getCurrentTenantSlug();
  if (!slug) return { title: 'О нас' };
  const tenant = await resolveTenant(slug);
  return {
    title: `О нас — ${tenant?.brandName ?? tenant?.name ?? ''}`,
  };
}

export default async function AboutPage() {
  const slug = await getCurrentTenantSlug();
  if (!slug) {
    return <NotFound />;
  }

  const tenant = await resolveTenant(slug);
  if (!tenant) {
    return <NotFound />;
  }

  const org = await fetchPublicOrganization(tenant);

  return (
    <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6 sm:py-16">
      <h1 className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
        О нас
      </h1>
      <div className="mt-8">
        <MarkdownContent content={org.aboutText} />
      </div>
    </div>
  );
}

function NotFound() {
  return (
    <div className="flex min-h-[50vh] items-center justify-center">
      <p className="text-muted-foreground">Организация не найдена</p>
    </div>
  );
}