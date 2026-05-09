/**
 * TenantFooter — подвал витрины с брендингом.
 */
import Link from 'next/link';

interface TenantFooterProps {
  brandName: string | null;
  orgName: string;
}

export function TenantFooter({ brandName, orgName }: TenantFooterProps) {
  const displayName = brandName ?? orgName;

  return (
    <footer className="border-t border-border bg-card/50">
      <div className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-8 text-sm text-muted-foreground sm:flex-row sm:justify-between sm:px-6">
        <p>
          © {new Date().getFullYear()} {displayName}
          <span className="mx-1.5 text-muted-foreground/50">&middot;</span>
          <span className="text-muted-foreground/60">
            на платформе TD Pay
          </span>
        </p>
        <nav className="flex flex-wrap gap-x-6 gap-y-2">
          <Link
            href="/about"
            className="hover:text-foreground transition-colors"
          >
            О нас
          </Link>
          <Link
            href="/contacts"
            className="hover:text-foreground transition-colors"
          >
            Контакты
          </Link>
          <Link
            href="/terms"
            className="hover:text-foreground transition-colors"
          >
            Оферта
          </Link>
          <Link
            href="/privacy"
            className="hover:text-foreground transition-colors"
          >
            Конфиденциальность
          </Link>
        </nav>
      </div>
    </footer>
  );
}