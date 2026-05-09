/**
 * Типы API-контракта.
 * Синхронизированы вручную с Pydantic-схемами бэкенда.
 * Источник истины: backend/src/paytools/api/v1/schemas/
 * openapi-gen планируется после стабилизации контракта.
 */

// ---- Auth ----

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenPair {
  access_token: string;
  token_type: 'bearer';
  expires_in: number;
}

export interface MagicLinkRequest {
  email: string;
}

export interface MagicLinkVerifyRequest {
  token: string;
}

/** GET /api/v1/auth/me → MeResponse */
export interface UserProfile {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  role: 'organizer' | 'superadmin' | 'scanner' | 'cashier' | 'support';
  organization_id: string | null;
  organization_slug: string | null;
  organization_status: 'pending_moderation' | 'active' | 'suspended' | null;
}

/** GET /api/v1/organizer/organization → OrganizationRead */
export interface OrganizationProfile {
  id: string;
  name: string;
  slug: string;
  status: 'pending_moderation' | 'active' | 'suspended';
  brand_name: string | null;
  brand_color: string | null;
  logo_url: string | null;
  legal_entity_type: string | null;
  legal_inn: string | null;
  legal_name: string | null;
  legal_address: string | null;
  qrm_api_key_masked: string | null;
  qrm_api_login: string | null;
  qrm_prod_mode: boolean;
  telegram_chat_id: number | null;
  contact_email: string | null;
  contact_phone: string | null;
  refund_policy: string | null;
  auto_publish_enabled: boolean;
  timezone: string;
  created_at: string;
  updated_at: string;
}

export interface SessionData {
  user: UserProfile;
  organization: OrganizationProfile | null;
}

// ---- Registration ----

/** POST /api/v1/public/organizations/register → OrganizationRegisterRequest */
export interface RegisterRequest {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  organization_name: string;
  organization_slug: string;
  accept_terms: boolean;
}

export interface RegisterResponse {
  organization_id: string;
  user_id: string;
  status: 'pending_moderation';
  message: string;
}

// ---- Tenant ----

export interface TenantResolveResponse {
  id: string;
  slug: string;
  name: string;
  brand_name: string | null;
  brand_color: string | null;
  logo_url: string | null;
  status: string;
}

// ---- Organization Settings ----

/** PATCH /api/v1/organizer/organization → OrganizationUpdateRequest */
export interface OrganizationUpdateRequest {
  brand_name?: string | null;
  brand_color?: string | null;
  logo_url?: string | null;
  legal_entity_type?: string | null;
  legal_inn?: string | null;
  legal_name?: string | null;
  legal_address?: string | null;
  qrm_api_key?: string | null;
  qrm_api_login?: string | null;
  qrm_prod_mode?: boolean;
  telegram_chat_id?: number | null;
  contact_email?: string | null;
  contact_phone?: string | null;
  refund_policy?: string | null;
  timezone?: string | null;
}

export interface QrmTestResponse {
  ok: boolean;
  message: string;
  details?: Record<string, unknown> | null;
}

// ---- Admin ----

export interface AdminOrganization {
  id: string;
  name: string;
  slug: string;
  owner_email: string;
  status: 'pending_moderation' | 'active' | 'suspended';
  created_at: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  pagination: {
    page: number;
    per_page: number;
    total: number;
    total_pages: number;
  };
}

export interface SuspendRequest {
  reason: string;
}

// ---- Events ----

export type EventStatus =
  | 'draft'
  | 'pending_moderation'
  | 'published'
  | 'rejected'
  | 'archived';

export type ScheduleType = 'single' | 'sessions' | 'period';

/** Один сеанс в расписании sessions (синхронизировано с SessionItem в validation.py). */
export interface SessionItem {
  id: string;
  starts_at: string;
  ends_at: string;
}

/** Расписание: discriminated union по type (синхронизировано с Schedule в validation.py). */
export type EventSchedule =
  | { type: 'single'; starts_at: string; ends_at: string }
  | { type: 'sessions'; sessions: SessionItem[] }
  | { type: 'period'; starts_at: string; ends_at: string };

// ---- Capacity Policy (discriminated union, синхронизировано с validation.py) ----

export type CapacityPolicy =
  | { type: 'unlimited' }
  | { type: 'total'; limit: number }
  | { type: 'per_tariff' }
  | { type: 'hybrid'; total: number };

// ---- Custom Fields (синхронизировано с CustomFieldSchema в validation.py) ----

export type CustomFieldType =
  | 'text'
  | 'textarea'
  | 'number'
  | 'select'
  | 'multiselect'
  | 'checkbox'
  | 'date';

export interface CustomField {
  id: string;
  label: string;
  type: CustomFieldType;
  required: boolean;
  /** Варианты для select/multiselect */
  options?: string[];
  /** Макс. длина для text/textarea */
  max_length?: number;
}

// ---- Tariffs ----

export interface EventTariff {
  id: string;
  event_id: string;
  name: string;
  description?: string;
  /** Цена в копейках (0 = бесплатно) */
  price_kopecks: number;
  /** Лимит мест (null = безлимит) */
  capacity_limit: number | null;
  is_active: boolean;
  is_complimentary: boolean;
  sort_order: number;
  sold_count: number;
  created_at: string;
}

export interface TariffCreateRequest {
  name: string;
  description?: string;
  price_kopecks: number;
  capacity_limit?: number;
  is_complimentary?: boolean;
  sort_order?: number;
  is_active?: boolean;
}

export interface TariffUpdateRequest {
  name?: string;
  description?: string;
  price_kopecks?: number;
  capacity_limit?: number;
  is_complimentary?: boolean;
  sort_order?: number;
  is_active?: boolean;
}

// ---- Event CRUD ----

export interface EventItem {
  id: string;
  organization_id: string;
  slug: string;
  title: string;
  description_md?: string;
  location_name: string;
  location_address?: string;
  schedule: EventSchedule;
  capacity_policy: CapacityPolicy;
  sold_count: number;
  image_card_url?: string;
  image_background_url?: string;
  custom_fields_schema?: CustomField[];
  status: EventStatus;
  moderation_note?: string;
  /** Цена «от» в копейках (минимальная среди активных тарифов) */
  price_from_kopecks?: number;
  /** Есть ли места (sold_count < capacity) */
  is_sold_out?: boolean;
  created_at: string;
  updated_at: string;
}

/** API-ответ: список событий с пагинацией. */
export interface EventsListResponse {
  items: EventItem[];
  pagination: {
    page: number;
    per_page: number;
    total: number;
    total_pages: number;
  };
}

/** Фильтры для списка событий. */
export interface EventsFilters {
  status?: EventStatus[];
  from?: string;
  to?: string;
  search?: string;
  page?: number;
  per_page?: number;
}

/** Запрос на создание/обновление события. */
export interface EventCreateRequest {
  title: string;
  slug: string;
  description_md?: string;
  location_name: string;
  location_address?: string;
  schedule: EventSchedule;
  capacity_policy: CapacityPolicy;
  custom_fields_schema?: CustomField[];
}

export type EventUpdateRequest = Partial<EventCreateRequest>;

/** Ответ на запрос деталей события (с тарифами). */
export interface EventDetailResponse extends EventItem {
  tariffs: EventTariff[];
}

/** Ответ загрузки изображения. */
export interface ImageUploadResponse {
  url: string;
  kind: 'card' | 'background';
}

// ---- Public Events (Phase 3c — витрина) ----

/** Элемент списка событий для каталога витрины. */
export interface PublicEventListItem {
  id: string;
  slug: string;
  title: string;
  schedule: EventSchedule;
  location_name: string | null;
  image_card_url: string | null;
  price_from_kopecks: number | null;
  is_sold_out: boolean;
}

/** Тариф для публичной витрины. */
export interface PublicTariff {
  id: string;
  name: string;
  description: string | null;
  price_kopecks: number;
  capacity_limit: number | null;
  sold_count: number;
  is_active: boolean;
}

/** Детали события для страницы витрины. */
export interface PublicEventDetail {
  id: string;
  slug: string;
  title: string;
  description_md: string | null;
  schedule: EventSchedule;
  location_name: string | null;
  location_address: string | null;
  image_card_url: string | null;
  image_background_url: string | null;
  capacity_policy: CapacityPolicy;
  custom_fields_schema: CustomField[];
  tariffs: PublicTariff[];
  price_from_kopecks: number | null;
  is_sold_out: boolean;
  status: string;
}

// ---- Reservations (Phase 4) ----

export interface ReservationItemRequest {
  tariff_id: string;
  quantity: number;
}

export interface CreateReservationRequest {
  event_id: string;
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  items: ReservationItemRequest[];
  custom_fields?: Record<string, unknown>;
  promo_code?: string;
  consent_privacy: boolean;
  consent_offer: boolean;
}

export interface ReservationItemResponse {
  id: string;
  tariff_id: string;
  tariff_name: string;
  quantity: number;
  price_kopecks: number;
  subtotal_kopecks: number;
}

export interface ReservationResponse {
  id: string;
  status: 'pending_payment' | 'paid' | 'cancelled' | 'expired';
  event_id: string;
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  total_kopecks: number;
  items_subtotal_kopecks: number;
  discount_kopecks: number;
  promo_code_id: string | null;
  expires_at: string;
  items: ReservationItemResponse[];
}

// ---- PromoCode validation (Phase 4) ----

export interface PromoValidateItem {
  tariff_id: string;
  quantity: number;
}

export interface PromoValidateRequest {
  code: string;
  event_id: string;
  email: string;
  items: PromoValidateItem[];
}

export interface PromoValidateResponse {
  valid: boolean;
  discount_type?: 'percent' | 'fixed_amount' | 'fixed_price';
  discount_value?: number;
  discount_kopecks?: number;
  code?: string;
  description?: string;
  error_code?: string;
  error_message?: string;
}

// ---- Payments (Phase 5) ----

export type PaymentStatus = 'pending' | 'paid' | 'cancelled' | 'expired' | 'refunded';

export interface PaymentStatusResponse {
  payment_id: string | null;
  reservation_id: string;
  status: PaymentStatus;
  amount_kopecks: number;
  currency: string;
  provider: 'qrmanager' | 'complimentary' | 'cash' | null;
  qr_url: string | null;
  qr_image_url: string | null;
  expires_at: string | null;
  paid_at: string | null;
}

export interface PaymentProcessResponse {
  payment_id: string;
  reservation_id: string;
  status: PaymentStatus;
  amount_kopecks: number;
  currency: string;
  qr_url: string | null;
  qr_image_base64: string | null;
  expires_at: string;
}

// ---- Tickets (Phase 5) ----

export interface TicketItem {
  id: string;
  code: string;
  guest_index: number;
  guest_first_name: string;
  guest_last_name: string;
  status: 'issued' | 'checked_in' | 'cancelled' | 'refunded';
  is_complimentary: boolean;
}

// ---- API Error ----

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
    request_id?: string;
  };
}