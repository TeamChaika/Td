/**
 * TenantHeader — шапка витрины с брендингом организации.
 * Показывает логотип (если есть), brand_name и навигацию.
 */
import Image from 'next/image';
import Link from 'next/link';

import { cn } from '@/lib/utils/cn';

interface TenantHeaderProps {
  brandName: string | null;
  brandColor: string | null;
  logoUrl: string | null;
  /** Имя организации (fallback если нет brand_name) */
  orgName: string;
}

export function TenantHeader({
  brandName,
  brandColor,
  logoUrl,
  orgName,
}: TenantHeaderProps) {
  const displayName = brandName ?? orgName;

  return (
    <header className="sticky top-0 z-30 border-b border-border bg-background/80 backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 sm:px-6">
        {/* Logo + Name */}
        <Link
          href="/"
          className="flex items-center gap-3 min-w-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--brand,theme(colors.blue.400))] rounded-md"
        >
          {logoUrl ? (
            <Image
              src={logoUrl}
              alt={displayName}
              width={36}
              height={36}
              className="h-9 w-9 rounded object-contain shrink-0"
            />
          ) : (
            <div
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md text-white text-sm font-bold"
              style={{ backgroundColor: brandColor ?? '#3b82f6' }}
              aria-hidden
            >
              {displayName.charAt(0).toUpperCase()}
            </div>
          )}
          <span className="text-base font-semibold text-foreground truncate">
            {displayName}
          </span>
        </Link>

        {/* Navigation */}
        <nav className="hidden sm:flex items-center gap-1">
          <NavLink href="/">События</NavLink>
          <NavLink href="/about">О нас</NavLink>
          <NavLink href="/contacts">Контакты</NavLink>
        </nav>

        {/* Mobile menu placeholder — в MVP просто ссылки */}
        <div className="flex sm:hidden items-center gap-3">
          <Link
            href="/about"
            className="text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            О нас
          </Link>
          <Link
            href="/contacts"
            className="text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            Контакты
          </Link>
        </div>
      </div>
    </header>
  );
}

function NavLink({
  href,
  children,
}: {
  href: string;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      className={cn(
        'px-3 py-1.5 text-sm rounded-md transition-colors',
        'text-muted-foreground hover:text-foreground hover:bg-accent',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--brand,theme(colors.blue.400))]',
      )}
    >
      {children}
    </Link>
  );
}