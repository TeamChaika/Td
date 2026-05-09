/**
 * Страница оплаты: /pay/{reservation_id}
 *
 * Phase 4: заглушка — в Phase 5 будет реализована QRM-оплата (QR + polling).
 */
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Оплата',
  robots: { index: false },
};

interface PayPageProps {
  params: Promise<{ id: string }>;
}

export default async function PayPage({ params }: PayPageProps) {
  const { id } = await params;

  return (
    <div className="mx-auto max-w-md px-4 py-16 text-center">
      <h1 className="text-2xl font-bold mb-4">Оплата</h1>
      <p className="text-muted-foreground mb-2">
        Бронирование <span className="font-mono text-xs">{id}</span> создано.
      </p>
      <p className="text-muted-foreground text-sm">
        Оплата через QRM будет доступна в следующей версии (Phase 5).
      </p>
    </div>
  );
}
