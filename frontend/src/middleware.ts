/**
 * Middleware:
 *  1. Определяет арендатора по subdomain и пробрасывает slug в заголовке.
 *  2. Защищает /admin/* (кроме /admin/login, /admin/magic-link) — проверка refresh cookie.
 *  3. Защищает /platform/* (кроме /platform/login) — проверка refresh cookie.
 *
 *  Refresh token живёт в httpOnly cookie tdpay_refresh, path=/api/v1/auth.
 *  На middleware уровне проверяем только наличие cookie — роль валидируется в layout
 *  через useSession + /api/v1/auth/me.
 */
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

const PLATFORM_DOMAIN = process.env.NEXT_PUBLIC_PLATFORM_DOMAIN ?? 'tdpay.ru';

function extractSlug(hostname: string): string | null {
  const lower = hostname.toLowerCase();
  if (lower === PLATFORM_DOMAIN || lower === `www.${PLATFORM_DOMAIN}`) return null;

  const platformSuffix = `.${PLATFORM_DOMAIN}`;
  if (lower.endsWith(platformSuffix)) {
    const slug = lower.slice(0, -platformSuffix.length);
    if (slug && !slug.includes('.')) return slug;
  }

  if (lower.endsWith('.localhost')) {
    const slug = lower.slice(0, -'.localhost'.length);
    if (slug && !slug.includes('.')) return slug;
  }

  return null;
}

/** Проверить наличие refresh cookie. */
function hasRefreshCookie(req: NextRequest): boolean {
  return req.cookies.has('tdpay_refresh');
}

export function middleware(req: NextRequest): NextResponse {
  const host = req.headers.get('host') ?? '';
  const hostname = host.split(':')[0] ?? '';
  const pathname = req.nextUrl.pathname;

  // ---- Admin protection ----
  if (pathname.startsWith('/admin')) {
    // Публичные admin-роуты
    if (pathname === '/admin/login' || pathname === '/admin/magic-link') {
      // Если уже залогинен — редирект в /admin
      if (hasRefreshCookie(req)) {
        return NextResponse.redirect(new URL('/admin', req.url));
      }
      return NextResponse.next();
    }

    // Защищённые admin-роуты
    if (!hasRefreshCookie(req)) {
      const loginUrl = new URL('/admin/login', req.url);
      loginUrl.searchParams.set('from', pathname);
      return NextResponse.redirect(loginUrl);
    }

    return NextResponse.next();
  }

  // ---- Platform protection ----
  if (pathname.startsWith('/platform')) {
    if (pathname === '/platform/login') {
      if (hasRefreshCookie(req)) {
        return NextResponse.redirect(new URL('/platform', req.url));
      }
      return NextResponse.next();
    }

    if (!hasRefreshCookie(req)) {
      const loginUrl = new URL('/platform/login', req.url);
      loginUrl.searchParams.set('from', pathname);
      return NextResponse.redirect(loginUrl);
    }

    return NextResponse.next();
  }

  // ---- Tenant detection (for public routes) ----
  if (pathname.startsWith('/scanner')) {
    return NextResponse.next();
  }

  const slug = extractSlug(hostname);
  const response = NextResponse.next();
  if (slug) {
    response.headers.set('x-tenant-slug', slug);
  }
  return response;
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico|api|.*\\..*).*)'],
};