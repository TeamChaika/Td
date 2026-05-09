/**
 * TenantLayout — обёртка для всех страниц витрины арендатора.
 * Применяет брендинг (цвет, логотип), header и footer.
 *
 * Используется:
 * - В (tenant)/layout.tsx для всех tenant-страниц
 * - В root page.tsx для каталога (главной страницы витрины)
 */
import type { ReactNode } from 'react';

import { TenantHeader } from './tenant-header';
import { TenantFooter } from './tenant-footer';

export interface TenantContext {
  slug: string;
  name: string;
  brandName: string | null;
  brandColor: string | null;
  logoUrl: string | null;
}

interface TenantLayoutProps {
  tenant: TenantContext;
  children: ReactNode;
}

export function TenantLayout({ tenant, children }: TenantLayoutProps) {
  return (
    <>
      {/* Брендовый цвет через CSS-переменную */}
      <style
        dangerouslySetInnerHTML={{
          __html: tenant.brandColor
            ? `:root { --brand: ${tenant.brandColor}; }`
            : '',
        }}
      />

      <div className="flex min-h-screen flex-col">
        <TenantHeader
          brandName={tenant.brandName}
          brandColor={tenant.brandColor}
          logoUrl={tenant.logoUrl}
          orgName={tenant.name}
        />

        <main className="flex-1">{children}</main>

        <TenantFooter
          brandName={tenant.brandName}
          orgName={tenant.name}
        />
      </div>
    </>
  );
}