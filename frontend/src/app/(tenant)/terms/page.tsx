/**
 * Страница «Оферта» — /terms
 * Работает и на tdpay.ru (лендинг), и на *.tdpay.ru (витрина).
 */
import type { Metadata } from 'next';

import { getCurrentTenantSlug, resolveTenant } from '@/lib/tenant/resolve';
import { fetchPublicOrganization } from '@/lib/api/public-organization';
import { MarkdownContent } from '@/features/events/public';

const PLATFORM_TERMS = `## Условия использования платформы TD Pay

### 1. Общие положения

TD Pay — SaaS-платформа для продажи билетов на мероприятия. Используя платформу, вы соглашаетесь с настоящими условиями.

### 2. Регистрация

Для использования платформы необходимо зарегистрироваться, указав достоверные данные об организации. Администрация оставляет за собой право отказать в регистрации без объяснения причин.

### 3. Комиссия

Платформа взимает комиссию в размере 0.8% от стоимости проданных билетов. Комиссия списывается с внутреннего кошелька организатора.

### 4. Ответственность

Платформа не несёт ответственности за содержание мероприятий, качество услуг организатора и взаиморасчёты между организатором и покупателями билетов.`;

export async function generateMetadata(): Promise<Metadata> {
  const slug = await getCurrentTenantSlug();
  if (!slug) return { title: 'Оферта · TD Pay' };
  const tenant = await resolveTenant(slug);
  return {
    title: `Оферта — ${tenant?.brandName ?? tenant?.name ?? ''}`,
  };
}

export default async function TermsPage() {
  const slug = await getCurrentTenantSlug();

  if (!slug) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6 sm:py-16">
        <h1 className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
          Условия использования
        </h1>
        <div className="mt-8">
          <MarkdownContent content={PLATFORM_TERMS} />
        </div>
      </div>
    );
  }

  const tenant = await resolveTenant(slug);
  if (!tenant) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <p className="text-muted-foreground">Организация не найдена</p>
      </div>
    );
  }

  const org = await fetchPublicOrganization(tenant);

  return (
    <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6 sm:py-16">
      <h1 className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
        Условия возврата
      </h1>
      <div className="mt-8">
        <MarkdownContent content={org.refundPolicy} />
      </div>
    </div>
  );
}