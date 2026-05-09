/**
 * API-функции для публичных эндпоинтов бронирований и промокодов.
 *
 * Endpoints:
 *   POST /api/v1/public/reservations       — создание брони
 *   POST /api/v1/public/promocodes/validate — валидация промокода
 */
import { api } from '@/lib/api/client';
import type {
  CreateReservationRequest,
  ReservationResponse,
  PromoValidateRequest,
  PromoValidateResponse,
} from '@/types/api';

/** Создать бронирование. */
export async function createReservation(
  data: CreateReservationRequest,
  tenantSlug: string,
  idempotencyKey?: string,
): Promise<ReservationResponse> {
  const headers: Record<string, string> = { 'X-Tenant-Slug': tenantSlug };
  if (idempotencyKey) {
    headers['Idempotency-Key'] = idempotencyKey;
  }

  return api<ReservationResponse>('/api/v1/public/reservations', {
    method: 'POST',
    body: data,
    headers,
  });
}

/** Валидировать промокод (без применения). */
export async function validatePromoCode(
  data: PromoValidateRequest,
  tenantSlug: string,
): Promise<PromoValidateResponse> {
  return api<PromoValidateResponse>('/api/v1/public/promocodes/validate', {
    method: 'POST',
    body: data,
    headers: { 'X-Tenant-Slug': tenantSlug },
  });
}
