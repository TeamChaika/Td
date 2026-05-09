'use client';

/**
 * Layout суперадмина платформы.
 * Защита: useSession + проверка роли superadmin.
 * Sidebar: Организации / Модерация событий / Биллинг / Аудит.
 */
import { useState, useEffect, type ReactNode } from 'react';
import Link from 'next/link';
import { useRouter, usePathname } from 'next/navigation';

import { ConfirmDialog } from '@/components/ui/confirm-dialog';
import { Spinner } from '@/components/ui/spinner';
import { useSession } from '@/lib/auth/use-session';
import { useLogout } from '@/lib/auth/use-logout';
import { cn } from '@/lib/utils/cn';

const NAV: { href: string; label: string; enabled: boolean }[] = [
  { href: '/platform/organizations', label: 'Организации', enabled: true },
  { href: '/platform/moderation', label: 'Модерация событий', enabled: false },
  { href: '/platform/billing', label: 'Биллинг', enabled: false },
  { href: '/platform/audit', label: 'Аудит', enabled: false },
];

export default function PlatformLayout({ children }: { children: ReactNode }) {
  const { user, isAuthenticated, loading } = useSession();
  const logout = useLogout('/platform/login');
  const router = useRouter();
  const pathname = usePathname();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);

  // Редирект если не авторизован или не superadmin.
  // При неверной роли сначала делаем logout (очищаем куку),
  // чтобы избежать бесконечного цикла: middleware видит куку → пускает →
  // layout редиректит → middleware снова пускает.
  useEffect(() => {
    if (!loading) {
      if (!isAuthenticated) {
        router.replace('/platform/login');
      } else if (user?.role !== 'superadmin') {
        logout.mutate();
      }
    }
  }, [loading, isAuthenticated, user, router, logout]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  if (!isAuthenticated || user?.role !== 'superadmin') {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner size="lg" />
        <p className="ml-3 text-muted-foreground">Проверка доступа...</p>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/60 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-50 w-60 shrink-0 border-r border-border bg-card transition-transform',
          'md:sticky md:top-0 md:translate-x-0',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <div className="px-6 py-5">
          <Link href="/platform/organizations" className="text-xl font-bold">
            TD Pay
          </Link>
          <p className="mt-1 text-xs text-muted-foreground">
            Суперадмин платформы
          </p>
        </div>
        <nav className="flex flex-col gap-1 px-3 py-2">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.enabled ? item.href : '#'}
              onClick={() => setSidebarOpen(false)}
              className={cn(
                'rounded-md px-3 py-2 text-sm transition-colors',
                !item.enabled && 'cursor-not-allowed opacity-40',
                pathname === item.href && item.enabled
                  ? 'bg-accent text-accent-foreground font-medium'
                  : 'hover:bg-accent hover:text-accent-foreground',
              )}
              aria-disabled={!item.enabled}
            >
              <span className="flex items-center gap-2">
                {item.label}
                {!item.enabled && (
                  <span className="text-[10px] text-muted-foreground">Скоро</span>
                )}
              </span>
            </Link>
          ))}
        </nav>
      </aside>

      {/* Content */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="flex h-14 shrink-0 items-center justify-between border-b border-border px-4 md:px-6">
          <button
            className="md:hidden p-1.5 rounded hover:bg-accent"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            aria-label="Меню"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          <span className="text-sm font-medium">
            {user?.first_name} {user?.last_name} · Суперадмин
          </span>
          <button
            onClick={() => setShowLogoutConfirm(true)}
            className="text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            Выйти
          </button>
        </header>

        <div className="flex-1 p-4 md:p-6">{children}</div>
      </div>

      <ConfirmDialog
        open={showLogoutConfirm}
        onOpenChange={setShowLogoutConfirm}
        title="Выйти из аккаунта?"
        confirmLabel="Выйти"
        variant="destructive"
        onConfirm={() => logout.mutate()}
      />
    </div>
  );
}