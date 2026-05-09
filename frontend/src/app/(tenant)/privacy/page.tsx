/**
 * Страница «Политика конфиденциальности» — /privacy
 * Работает и на tdpay.ru (лендинг), и на *.tdpay.ru (витрина).
 */
import type { Metadata } from 'next';

import { getCurrentTenantSlug, resolveTenant } from '@/lib/tenant/resolve';
import { fetchPublicOrganization } from '@/lib/api/public-organization';
import { MarkdownContent } from '@/features/events/public';

const PLATFORM_PRIVACY = `## Политика конфиденциальности TD Pay

### 1. Какие данные мы собираем

При регистрации и использовании платформы мы можем запрашивать:
- Email и пароль для входа в личный кабинет
- Имя и фамилию
- Данные об организации (название, ИНН, юридический адрес)

### 2. Как мы используем данные

- Для предоставления доступа к платформе
- Для связи по вопросам работы сервиса
- Для выставления счетов и отчётности

### 3. Хранение данных

Данные хранятся на серверах на территории РФ в соответствии с 152-ФЗ.

### 4. Передача третьим лицам

Мы не передаём данные третьим лицам без вашего согласия, за исключением случаев, предусмотренных законодательством.`;

export async function generateMetadata(): Promise<Metadata> {
  const slug = await getCurrentTenantSlug();
  if (!slug) return { title: 'Политика конфиденциальности · TD Pay' };
  const tenant = await resolveTenant(slug);
  return {
    title: `Политика конфиденциальности — ${tenant?.brandName ?? tenant?.name ?? ''}`,
  };
}

export default async function PrivacyPage() {
  const slug = await getCurrentTenantSlug();

  if (!slug) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6 sm:py-16">
        <h1 className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
          Политика конфиденциальности
        </h1>
        <div className="mt-8">
          <MarkdownContent content={PLATFORM_PRIVACY} />
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
        Политика конфиденциальности
      </h1>
      <div className="mt-8">
        <MarkdownContent content={org.privacyPolicy} />
      </div>
    </div>
  );
}