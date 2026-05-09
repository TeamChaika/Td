/**
 * Публичные компоненты событий.
 * Экспортируются для переиспользования в витрине (3c) и admin preview (3b).
 */

export { EventCard, EventCardSkeleton } from './event-card';
export { EventList } from './event-list';
export { EventHero, EventHeroSkeleton } from './event-hero';
export { TariffsList } from './tariffs-list';
export { MarkdownContent } from './markdown-content';
export { BuyTicketCTA } from './buy-ticket-cta';
export { TenantHeader } from './tenant-header';
export { TenantFooter } from './tenant-footer';
export { TenantLayout } from './tenant-layout';
export type { TenantContext } from './tenant-layout';
export { formatSchedule, formatScheduleShort } from './schedule-format';
