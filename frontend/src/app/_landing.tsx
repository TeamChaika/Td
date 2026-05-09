/**
 * Лендинг платформы TD Pay (корневой домен tdpay.ru).
 * В Phase 1 — статическая заглушка, в Phase 2 появится форма регистрации.
 */
import Link from 'next/link';

import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';

export function LandingPage() {
  return (
    <main className="min-h-screen">
      {/* Hero */}
      <section className="border-b border-border">
        <div className="mx-auto flex max-w-5xl flex-col items-center px-6 py-20 text-center md:py-32">
          <h1 className="text-4xl font-bold tracking-tight md:text-6xl">
            TD Pay
          </h1>
          <p className="mt-4 max-w-2xl text-balance text-lg text-muted-foreground md:text-xl">
            SaaS-платформа для продажи билетов на мероприятия и приёма депозитов.
            СБП-оплата, бренд организатора, QR-сканер на входе.
          </p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Button asChild size="lg">
              <Link href="/register">Стать организатором</Link>
            </Button>
            <Button asChild variant="outline" size="lg">
              <Link href="/admin/login">Вход в кабинет</Link>
            </Button>
          </div>
        </div>
      </section>

      {/* Фичи */}
      <section className="mx-auto max-w-5xl px-6 py-20">
        <h2 className="text-3xl font-semibold">Что умеет платформа</h2>
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">СБП через QR Manager</CardTitle>
            </CardHeader>
            <CardContent>
              <CardDescription>
                Приём оплаты по СБП на ваш расчётный счёт. Комиссия платформы
                — 0.8%, комиссия эквайринга — 0.7%.
              </CardDescription>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Свой поддомен</CardTitle>
            </CardHeader>
            <CardContent>
              <CardDescription>
                Витрина событий на `{`<your-brand>.tdpay.ru`}` с вашим логотипом
                и цветом. White-label с собственным доменом — в v1.1.
              </CardDescription>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Сканер на входе</CardTitle>
            </CardHeader>
            <CardContent>
              <CardDescription>
                PWA-приложение для контролёров. Камера телефона сканирует QR
                билета и подтверждает вход за долю секунды.
              </CardDescription>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border">
        <div className="mx-auto flex max-w-5xl flex-col gap-4 px-6 py-8 text-sm text-muted-foreground sm:flex-row sm:justify-between">
          <p>© 2026 TD Pay</p>
          <nav className="flex gap-6">
            <Link href="/terms" className="hover:text-foreground">
              Оферта
            </Link>
            <Link href="/privacy" className="hover:text-foreground">
              Политика конфиденциальности
            </Link>
          </nav>
        </div>
      </footer>
    </main>
  );
}
