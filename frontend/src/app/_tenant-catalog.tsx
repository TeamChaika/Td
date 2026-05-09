/**
 * TenantCatalogPage — главная страница витрины (каталог событий).
 * Рендерится из root page.tsx когда определён tenant.
 */
import { fetchPublicEvents } from '@/lib/api/public-events';
import Link from 'next/link';
import { TenantLayout, EventList } from '@/features/events/public';
import type { TenantContext } from '@/features/events/public';

interface TenantCatalogPageProps {
  tenant: TenantContext;
}

export async function TenantCatalogPage({ tenant }: TenantCatalogPageProps) {
  let events;
  let error: string | null = null;

  try {
    const data = await fetchPublicEvents(tenant.slug);
    events = data.items;
  } catch {
    error = 'Не удалось загрузить события. Пожалуйста, попробуйте позже.';
  }

  return (
    <TenantLayout tenant={tenant}>
      {/* Hero секция */}
      <section className="border-b border-border">
        <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6 sm:py-16 md:py-20">
          <h1 className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
            События {tenant.brandName ?? tenant.name}
          </h1>
          <p className="mt-2 max-w-2xl text-muted-foreground">
            Выбирайте мероприятие и бронируйте билеты онлайн
          </p>
        </div>
      </section>

      {/* Каталог */}
      <section className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-12">
        {error ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-destructive/10">
              <svg
                className="h-8 w-8 text-destructive"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={1.5}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"
                />
              </svg>
            </div>
            <h3 className="text-lg font-medium text-foreground">
              Что-то пошло не так
            </h3>
            <p className="mt-1 max-w-sm text-sm text-muted-foreground">
              {error}
            </p>
            <Link
              href="/"
              className="mt-4 text-sm font-medium"
              style={{ color: 'var(--brand, #3b82f6)' }}
            >
              Попробовать снова
            </Link>
          </div>
        ) : (
          <EventList events={events ?? []} />
        )}
      </section>
    </TenantLayout>
  );
}