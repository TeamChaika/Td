/**
 * Тип данных арендатора, резолвится на сервере по subdomain.
 */
export interface Tenant {
  slug: string;
  name: string;
  brandName: string | null;
  brandColor: string | null;
  logoUrl: string | null;
}
