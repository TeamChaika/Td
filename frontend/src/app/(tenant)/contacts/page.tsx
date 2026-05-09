/**
 * Страница «Контакты» — /contacts
 */
import type { Metadata } from 'next';

import { getCurrentTenantSlug, resolveTenant } from '@/lib/tenant/resolve';
import { fetchPublicOrganization } from '@/lib/api/public-organization';

export async function generateMetadata(): Promise<Metadata> {
  const slug = await getCurrentTenantSlug();
  if (!slug) return { title: 'Контакты' };
  const tenant = await resolveTenant(slug);
  return {
    title: `Контакты — ${tenant?.brandName ?? tenant?.name ?? ''}`,
  };
}

export default async function ContactsPage() {
  const slug = await getCurrentTenantSlug();
  if (!slug) {
    return <NotFound />;
  }

  const tenant = await resolveTenant(slug);
  if (!tenant) {
    return <NotFound />;
  }

  const org = await fetchPublicOrganization(tenant);

  const hasAnyContact =
    org.contactEmail || org.contactPhone || org.contactAddress;

  return (
    <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6 sm:py-16">
      <h1 className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
        Контакты
      </h1>

      {hasAnyContact ? (
        <div className="mt-8 space-y-6">
          {org.contactEmail && (
            <div className="flex items-start gap-3">
              <svg
                className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={1.5}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75"
                />
              </svg>
              <div>
                <p className="text-sm text-muted-foreground">Email</p>
                <a
                  href={`mailto:${org.contactEmail}`}
                  className="text-foreground hover:underline"
                  style={{ color: 'var(--brand, #3b82f6)' }}
                >
                  {org.contactEmail}
                </a>
              </div>
            </div>
          )}

          {org.contactPhone && (
            <div className="flex items-start gap-3">
              <svg
                className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={1.5}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M2.25 6.75c0 8.284 6.716 15 15 15h2.25a2.25 2.25 0 002.25-2.25v-1.372c0-.516-.351-.966-.852-1.091l-4.423-1.106c-.44-.11-.902.055-1.173.417l-.97 1.293c-.282.376-.769.542-1.21.38a12.035 12.035 0 01-7.143-7.143c-.162-.441.004-.928.38-1.21l1.293-.97c.363-.271.527-.734.417-1.173L6.963 3.102a1.125 1.125 0 00-1.091-.852H4.5A2.25 2.25 0 002.25 4.5v2.25z"
                />
              </svg>
              <div>
                <p className="text-sm text-muted-foreground">Телефон</p>
                <a
                  href={`tel:${org.contactPhone.replace(/\s/g, '')}`}
                  className="text-foreground hover:underline"
                >
                  {org.contactPhone}
                </a>
              </div>
            </div>
          )}

          {org.contactAddress && (
            <div className="flex items-start gap-3">
              <svg
                className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={1.5}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M15 10.5a3 3 0 11-6 0 3 3 0 016 0z"
                />
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1115 0z"
                />
              </svg>
              <div>
                <p className="text-sm text-muted-foreground">Адрес</p>
                <p className="text-foreground">{org.contactAddress}</p>
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="mt-8 rounded-lg border border-border bg-card p-8 text-center">
          <p className="text-muted-foreground">
            Контактная информация пока не добавлена.
          </p>
        </div>
      )}
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