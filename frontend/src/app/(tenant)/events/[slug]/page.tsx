/**
 * Страница деталей события: /events/{slug}
 *
 * SEO: generateMetadata с title, description, OG-тегами.
 * ISR: revalidate = 60 секунд.
 */
import type { Metadata } from 'next';
import { notFound } from 'next/navigation';

import { getCurrentTenantSlug } from '@/lib/tenant/resolve';
import { fetchPublicEvent } from '@/lib/api/public-events';
import {
  EventHero,
  MarkdownContent,
  TariffsList,
  BuyTicketCTA,
} from '@/features/events/public';

interface EventPageProps {
  params: Promise<{ slug: string }>;
}

export async function generateMetadata({
  params,
}: EventPageProps): Promise<Metadata> {
  const { slug: eventSlug } = await params;
  const tenantSlug = await getCurrentTenantSlug();

  if (!tenantSlug) return { title: 'Событие не найдено' };

  const event = await fetchPublicEvent(tenantSlug, eventSlug);
  if (!event) return { title: 'Событие не найдено' };

  const description = event.description_md
    ? event.description_md.replace(/[#*>`_\[\]()]/g, '').slice(0, 160)
    : `${event.title} — ${event.location_name ?? ''}`;

  return {
    title: event.title,
    description,
    openGraph: {
      title: event.title,
      description,
      type: 'article',
      images: event.image_background_url
        ? [{ url: event.image_background_url, width: 1600, height: 900 }]
        : [],
    },
    alternates: {
      canonical: `https://${tenantSlug}.tdpay.ru/events/${eventSlug}`,
    },
  };
}

export default async function EventPage({ params }: EventPageProps) {
  const { slug: eventSlug } = await params;
  const tenantSlug = await getCurrentTenantSlug();

  if (!tenantSlug) notFound();

  const event = await fetchPublicEvent(tenantSlug, eventSlug);

  if (!event || event.status !== 'published') notFound();

  return (
    <>
      <EventHero event={event} />

      <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-12">
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-[1fr_320px] lg:gap-12">
          {/* Основной контент */}
          <div className="min-w-0">
            {/* Описание */}
            <section>
              <h2 className="text-xl font-semibold text-foreground mb-4">
                О событии
              </h2>
              <MarkdownContent content={event.description_md} />
            </section>

            {/* Адрес */}
            {event.location_address && (
              <section className="mt-8">
                <h2 className="text-xl font-semibold text-foreground mb-3">
                  Адрес
                </h2>
                <p className="text-muted-foreground">
                  {event.location_address}
                </p>
              </section>
            )}
          </div>

          {/* Сайдбар: тарифы + CTA */}
          <aside className="space-y-6">
            {/* Desktop CTA */}
            <div className="hidden lg:block">
              <BuyTicketCTA
                eventSlug={event.slug}
                priceFromKopecks={event.price_from_kopecks}
                isSoldOut={event.is_sold_out}
                variant="inline"
              />
            </div>

            {/* Тарифы */}
            <section>
              <h2 className="text-lg font-semibold text-foreground mb-3">
                Тарифы
              </h2>
              <TariffsList tariffs={event.tariffs} />
            </section>
          </aside>
        </div>
      </div>

      {/* Mobile sticky CTA */}
      <BuyTicketCTA
        eventSlug={event.slug}
        priceFromKopecks={event.price_from_kopecks}
        isSoldOut={event.is_sold_out}
        variant="sticky-bottom"
      />
    </>
  );
}