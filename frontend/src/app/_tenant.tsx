/**
 * Главная страница витрины арендатора (*.tdpay.ru).
 * В Phase 1 — заглушка. В Phase 3 тут будет каталог событий.
 */
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import type { Tenant } from '@/types/tenant';

export function TenantHome({ tenant }: { tenant: Tenant }) {
  return (
    <main className="min-h-screen">
      <header className="border-b border-border">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-5">
          <div className="flex items-center gap-3">
            {tenant.logoUrl ? (
              // Логотип появится, когда будет загружен организатором
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={tenant.logoUrl}
                alt={tenant.name}
                className="h-8 w-8 rounded object-contain"
              />
            ) : (
              <div
                className="h-8 w-8 rounded bg-primary"
                aria-hidden
                style={
                  tenant.brandColor
                    ? { backgroundColor: tenant.brandColor }
                    : undefined
                }
              />
            )}
            <span className="text-lg font-semibold">
              {tenant.brandName ?? tenant.name}
            </span>
          </div>
          <span className="text-sm text-muted-foreground">
            на платформе TD Pay
          </span>
        </div>
      </header>

      <section className="mx-auto max-w-5xl px-6 py-10">
        <h1 className="text-3xl font-semibold tracking-tight">
          События {tenant.brandName ?? tenant.name}
        </h1>

        <Card className="mt-8">
          <CardHeader>
            <CardTitle className="text-lg">Пока нет опубликованных событий</CardTitle>
          </CardHeader>
          <CardContent>
            <CardDescription>
              Каталог и страницы мероприятий появятся в Phase 3 разработки.
              Пока это заглушка витрины арендатора.
            </CardDescription>
          </CardContent>
        </Card>
      </section>
    </main>
  );
}
