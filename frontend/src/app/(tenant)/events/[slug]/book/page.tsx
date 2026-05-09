/**
 * Страница бронирования: /events/{slug}/book
 *
 * Server component: загружает событие и передаёт клиентской форме.
 */
import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import Link from 'next/link';

import { getCurrentTenantSlug } from '@/lib/tenant/resolve';
import { fetchPublicEvent } from '@/lib/api/public-events';
import { BookingForm } from '@/features/booking/booking-form';

interface BookPageProps {
  params: Promise<{ slug: string }>;
}

export async function generateMetadata({ params }: BookPageProps): Promise<Metadata> {
  const { slug: eventSlug } = await params;
  const tenantSlug = await getCurrentTenantSlug();
  if (!tenantSlug) return { title: 'Бронирование' };

  const event = await fetchPublicEvent(tenantSlug, eventSlug);
  if (!event) return { title: 'Бронирование' };

  return {
    title: `Купить билет — ${event.title}`,
    robots: { index: false },
  };
}

export default async function BookPage({ params }: BookPageProps) {
  const { slug: eventSlug } = await params;
  const tenantSlug = await getCurrentTenantSlug();

  if (!tenantSlug) notFound();

  const event = await fetchPublicEvent(tenantSlug, eventSlug);

  if (!event || event.status !== 'published') notFound();

  if (event.is_sold_out) {
    // Если билетов нет — редиректим назад на страницу события
    notFound();
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-6 sm:px-6 sm:py-10">
      {/* Навигация */}
      <nav className="mb-6 text-sm text-muted-foreground">
        <Link href={`/events/${eventSlug}`} className="hover:text-foreground transition-colors">
          ← {event.title}
        </Link>
      </nav>

      <h1 className="text-2xl font-bold text-foreground mb-6">
        Оформление билета
      </h1>

      <BookingForm event={event} tenantSlug={tenantSlug} />
    </div>
  );
}
