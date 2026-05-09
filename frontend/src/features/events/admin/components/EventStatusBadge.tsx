'use client';

/**
 * EventStatusBadge — цветной бейдж статуса события.
 * Цвета: draft=серый, pending_moderation=жёлтый, published=зелёный,
 * rejected=красный, archived=нейтральный.
 */
import { Badge } from '@/components/ui/badge';
import type { EventStatus } from '@/types/api';

const STATUS_CONFIG: Record<
  EventStatus,
  { label: string; variant: 'default' | 'success' | 'warning' | 'destructive' }
> = {
  draft: { label: 'Черновик', variant: 'default' },
  pending_moderation: { label: 'На модерации', variant: 'warning' },
  published: { label: 'Опубликовано', variant: 'success' },
  rejected: { label: 'Отклонено', variant: 'destructive' },
  archived: { label: 'Архив', variant: 'default' },
};

interface EventStatusBadgeProps {
  status: EventStatus;
  className?: string;
}

export function EventStatusBadge({ status, className }: EventStatusBadgeProps) {
  const config = STATUS_CONFIG[status] ?? {
    label: status,
    variant: 'default' as const,
  };
  return (
    <Badge variant={config.variant} className={className}>
      {config.label}
    </Badge>
  );
}