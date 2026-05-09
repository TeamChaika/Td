/**
 * Хуки TanStack Query для CRUD событий.
 *
 * API-контракт: docs/API_CONTRACT.md § 3
 * Endpoints:
 *   GET    /api/v1/organizer/events           — список
 *   POST   /api/v1/organizer/events           — создать
 *   GET    /api/v1/organizer/events/{id}      — детали
 *   PATCH  /api/v1/organizer/events/{id}      — обновить
 *   DELETE /api/v1/organizer/events/{id}      — soft-delete (status=archived)
 *   POST   /api/v1/organizer/events/{id}/submit  — на модерацию
 *   POST   /api/v1/organizer/events/{id}/publish — опубликовать
 *   POST   /api/v1/organizer/events/{id}/images  — upload картинки
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api/client';
import type {
  EventItem,
  EventDetailResponse,
  EventsListResponse,
  EventsFilters,
  EventCreateRequest,
  EventUpdateRequest,
  ImageUploadResponse,
} from '@/types/api';

// ---- Ключи кэша ----

const eventsKeys = {
  all: ['events'] as const,
  lists: () => [...eventsKeys.all, 'list'] as const,
  list: (filters: EventsFilters) => [...eventsKeys.lists(), filters] as const,
  details: () => [...eventsKeys.all, 'detail'] as const,
  detail: (id: string) => [...eventsKeys.details(), id] as const,
};

// ---- Query: список событий ----

/** Преобразовать фильтры в query-параметры. */
function filtersToParams(filters: EventsFilters): URLSearchParams {
  const params = new URLSearchParams();
  if (filters.page) params.set('page', String(filters.page));
  if (filters.per_page) params.set('per_page', String(filters.per_page));
  if (filters.search) params.set('search', filters.search);
  if (filters.from) params.set('from', filters.from);
  if (filters.to) params.set('to', filters.to);
  if (filters.status) params.set('status', filters.status);
  return params;
}

export function useEvents(filters: EventsFilters) {
  return useQuery({
    queryKey: eventsKeys.list(filters),
    queryFn: async () => {
      const qs = filtersToParams(filters);
      qs.set('per_page', String(filters.per_page ?? 20));
      return api<EventsListResponse>(
        `/api/v1/organizer/events?${qs.toString()}`,
      );
    },
  });
}

// ---- Query: детали события ----

export function useEvent(id: string | undefined) {
  return useQuery({
    queryKey: eventsKeys.detail(id ?? ''),
    queryFn: () =>
      api<EventDetailResponse>(`/api/v1/organizer/events/${id}`),
    enabled: !!id,
  });
}

// ---- Mutations ----

export function useCreateEvent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: EventCreateRequest) =>
      api<EventItem>('/api/v1/organizer/events', {
        method: 'POST',
        body: data,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: eventsKeys.lists() });
    },
  });
}

export function useUpdateEvent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: EventUpdateRequest }) =>
      api<EventItem>(`/api/v1/organizer/events/${id}`, {
        method: 'PATCH',
        body: data,
      }),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: eventsKeys.detail(variables.id) });
      queryClient.invalidateQueries({ queryKey: eventsKeys.lists() });
    },
  });
}

export function useDeleteEvent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      api<void>(`/api/v1/organizer/events/${id}`, {
        method: 'DELETE',
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: eventsKeys.lists() });
    },
  });
}

export function useSubmitEvent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      api<EventItem>(`/api/v1/organizer/events/${id}/submit`, {
        method: 'POST',
      }),
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({ queryKey: eventsKeys.detail(id) });
      queryClient.invalidateQueries({ queryKey: eventsKeys.lists() });
    },
  });
}

export function usePublishEvent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      api<EventItem>(`/api/v1/organizer/events/${id}/publish`, {
        method: 'POST',
      }),
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({ queryKey: eventsKeys.detail(id) });
      queryClient.invalidateQueries({ queryKey: eventsKeys.lists() });
    },
  });
}

export function useUploadImage() {
  return useMutation({
    mutationFn: async ({
      eventId,
      file,
      kind,
    }: {
      eventId: string;
      file: File;
      kind: 'card' | 'background';
    }) => {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('kind', kind);
return api<ImageUploadResponse>(
        `/api/v1/organizer/events/${eventId}/images`,
        {
          method: 'POST',
          body: formData,
        },
      );
    },
  });
}
