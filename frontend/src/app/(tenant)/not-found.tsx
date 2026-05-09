/**
 * 404 страница для витрины арендатора.
 */
import Link from 'next/link';

export default function TenantNotFound() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center px-4 text-center">
      <p className="text-6xl font-bold text-muted-foreground/30">404</p>
      <h1 className="mt-4 text-2xl font-semibold text-foreground">
        Страница не найдена
      </h1>
      <p className="mt-2 max-w-md text-muted-foreground">
        Возможно, страница была удалена или вы перешли по неверной ссылке.
      </p>
      <Link
        href="/"
        className="mt-6 inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-colors"
        style={{
          backgroundColor: 'var(--brand, hsl(217 91% 60%))',
          color: 'white',
        }}
      >
        <svg
          className="h-4 w-4"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M10 19l-7-7m0 0l7-7m-7 7h18"
          />
        </svg>
        На главную
      </Link>
    </div>
  );
}