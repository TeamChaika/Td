/**
 * Зарезервированные slug-и, которые нельзя использовать при регистрации.
 * Синхронизировано с backend (docs/specs/phase-2-orgs-auth.md § Reserved slugs).
 */
export const RESERVED_SLUGS = new Set([
  'www',
  'admin',
  'api',
  'platform',
  'scanner',
  'app',
  'mail',
  'support',
  'help',
  'docs',
  'blog',
  'static',
  'assets',
  'cdn',
]);

/** Проверить, является ли slug зарезервированным. */
export function isReservedSlug(slug: string): boolean {
  return RESERVED_SLUGS.has(slug.toLowerCase());
}