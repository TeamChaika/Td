/**
 * Хуки TanStack Query для CRUD тарифов.
 *
 * API-контракт: docs/API_CONTRACT.md § 3 (Tariffs)
 * Endpoints:
 *   GET    /api/v1/organizer/events/{event_id}/tariffs
 *   POST   /api/v1/organizer/events/{event_id}/tariffs
 *   PATCH  /api/v1/organizer/tariffs/{id}
 *   DELETE /api/v1/organizer/tariffs/{id}
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api/client';
import type {
  EventTariff,
  TariffCreateRequest,
  TariffUpdateRequest,
} from '@/types/api';

const tariffKeys = {
  all: ['tariffs'] as const,
  byEvent: (eventId: string) => [...tariffKeys.all, 'event', eventId] as const,
};

export function useTariffs(eventId: string | undefined) {
  return useQuery({
    queryKey: tariffKeys.byEvent(eventId ?? ''),
    queryFn: () =>
      api<EventTariff[]>(
        `/api/v1/organizer/events/${eventId}/tariffs`,
      ),
    enabled: !!eventId,
  });
}

export function useCreateTariff() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      eventId,
      data,
    }: {
      eventId: string;
      data: TariffCreateRequest;
    }) =>
      api<EventTariff>(`/api/v1/organizer/events/${eventId}/tariffs`, {
        method: 'POST',
        body: data,
      }),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: tariffKeys.byEvent(variables.eventId) });
    },
  });
}

export function useUpdateTariff() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: TariffUpdateRequest }) =>
      api<EventTariff>(`/api/v1/organizer/tariffs/${id}`, {
        method: 'PATCH',
        body: data,
      }),
    onSuccess: () => {
      // Инвалидируем все запросы тарифов (не знаем event_id из контекста)
      queryClient.invalidateQueries({ queryKey: tariffKeys.all });
    },
  });
}

export function useDeleteTariff() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      api<void>(`/api/v1/organizer/tariffs/${id}`, {
        method: 'DELETE',
      }),
    onMutate: async (id) => {
      // Optimistic: удаляем тариф из кэша
      await queryClient.cancelQueries({ queryKey: tariffKeys.all });
      // Возвращаем id для rollback
      return { id };
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: tariffKeys.all });
    },
  });
}
