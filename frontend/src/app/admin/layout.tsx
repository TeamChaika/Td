'use client';

/**
 * Layout админки организатора.
 * Защищён: если сессия не загружена — редирект на /admin/login.
 * Sidebar с навигацией, header с именем и logout.
 */
import { useState, useEffect, type ReactNode } from 'react';
import Link from 'next/link';
import { useRouter, usePathname } from 'next/navigation';

import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Spinner } from '@/components/ui/spinner';
import { ConfirmDialog } from '@/components/ui/confirm-dialog';
import { useSession } from '@/lib/auth/use-session';
import { useLogout } from '@/lib/auth/use-logout';
import { cn } from '@/lib/utils/cn';

const NAV: { href: string; label: string; enabled: boolean }[] = [
  { href: '/admin', label: 'Dashboard', enabled: true },
  { href: '/admin/events', label: 'События', enabled: true },
  { href: '/admin/tariffs', label: 'Тарифы', enabled: false },
  { href: '/admin/promocodes', label: 'Промокоды', enabled: false },
  { href: '/admin/reservations', label: 'Брони', enabled: false },
  { href: '/admin/tickets', label: 'Билеты', enabled: false },
  { href: '/admin/billing', label: 'Биллинг', enabled: false },
  { href: '/admin/settings', label: 'Настройки', enabled: true },
];

export default function AdminLayout({ children }: { children: ReactNode }) {
  const { user, organization, isAuthenticated, loading } = useSession();
  const logout = useLogout('/admin/login');
  const router = useRouter();
  const pathname = usePathname();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);

  // Редирект если не авторизован или роль не organizer.
  // Не редиректим если уже на странице логина — иначе бесконечный цикл.
  const isLoginPage = pathname === '/admin/login' || pathname === '/admin/magic-link';

  useEffect(() => {
    if (loading || isLoginPage) return;
    if (!isAuthenticated || !user) {
      router.replace('/admin/login');
    } else if (user.role !== 'organizer' && user.role !== 'superadmin') {
      logout.mutate();
    }
  }, [loading, isAuthenticated, user, router, logout, isLoginPage]);

  // Для страниц логина/magic-link — рендерим как есть, без проверки сессии
  if (isLoginPage) {
    return <>{children}</>;
  }

  // Loading
  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  // Not authenticated
  if (!isAuthenticated) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner size="lg" />
        <p className="ml-3 text-muted-foreground">Проверка доступа...</p>
      </div>
    );
  }

  // Suspended organization
  if (organization?.status === 'suspended') {
    return (
      <div className="flex min-h-screen items-center justify-center px-6">
        <div className="max-w-md text-center space-y-4">
          <div className="rounded-lg border border-red-600/30 bg-red-600/10 p-8">
            <h1 className="text-2xl font-semibold text-red-400">Аккаунт заблокирован</h1>
            <p className="mt-4 text-muted-foreground">
              Ваша организация заблокирована администратором платформы.
              Свяжитесь с поддержкой для выяснения причин.
            </p>
            <Button
              variant="outline"
              className="mt-6"
              onClick={() => setShowLogoutConfirm(true)}
            >
              Выйти
            </Button>
          </div>
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
          <Link href="/admin" className="text-xl font-bold">
            TD Pay
          </Link>
          <p className="mt-1 text-xs text-muted-foreground">
            {organization?.brand_name || organization?.name || 'Кабинет организатора'}
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
        {/* Header */}
        <header className="flex h-14 shrink-0 items-center justify-between border-b border-border px-4 md:px-6">
          <div className="flex items-center gap-3">
            {/* Burger */}
            <button
              className="md:hidden p-1.5 rounded hover:bg-accent"
              onClick={() => setSidebarOpen(!sidebarOpen)}
              aria-label="Меню"
            >
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
            <span className="text-sm font-medium truncate">
              {user?.first_name} {user?.last_name}
            </span>
            {organization?.status === 'pending_moderation' && (
              <Badge variant="warning">На модерации</Badge>
            )}
          </div>
          <button
            onClick={() => setShowLogoutConfirm(true)}
            className="text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            Выйти
          </button>
        </header>

        {/* Pending moderation banner */}
        {organization?.status === 'pending_moderation' && (
          <div className="border-b border-amber-600/30 bg-amber-600/10 px-4 py-2 text-center text-sm text-amber-400">
            Ваша заявка на модерации — мы скоро с вами свяжемся.
          </div>
        )}

        {/* Page content */}
        <div className="flex-1 p-4 md:p-6">{children}</div>
      </div>

      {/* Logout confirm */}
      <ConfirmDialog
        open={showLogoutConfirm}
        onOpenChange={setShowLogoutConfirm}
        title="Выйти из аккаунта?"
        description="Вы будете перенаправлены на страницу входа."
        confirmLabel="Выйти"
        variant="destructive"
        onConfirm={() => logout.mutate()}
      />
    </div>
  );
}