/**
 * API-функции для публичных эндпоинтов платежей.
 *
 * Endpoints:
 *   GET  /api/v1/public/payments/{reservation_id}/status  — статус платежа
 *   POST /api/v1/public/payments/{reservation_id}/process  — создать QRM-платёж
 */
import { api } from '@/lib/api/client';
import type {
  PaymentStatusResponse,
  PaymentProcessResponse,
} from '@/types/api';

/** Получить статус платежа (поллинг). */
export async function getPaymentStatus(
  reservationId: string,
  tenantSlug: string,
): Promise<PaymentStatusResponse> {
  return api<PaymentStatusResponse>(
    `/api/v1/public/payments/${reservationId}/status`,
    { headers: { 'X-Tenant-Slug': tenantSlug } },
  );
}

/** Создать или получить QRM-платёж. */
export async function processPayment(
  reservationId: string,
  tenantSlug: string,
): Promise<PaymentProcessResponse> {
  return api<PaymentProcessResponse>(
    `/api/v1/public/payments/${reservationId}/process`,
    {
      method: 'POST',
      headers: { 'X-Tenant-Slug': tenantSlug },
    },
  );
}
