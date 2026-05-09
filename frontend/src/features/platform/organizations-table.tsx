'use client';

/**
 * Таблица организаций для суперадмина платформы.
 * Фильтр по статусу, actions: Approve, Suspend, View.
 */
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

import { Button } from '@/components/ui/button';
import { Select } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { ConfirmDialog } from '@/components/ui/confirm-dialog';
import { useToast } from '@/components/ui/toast';
import { api } from '@/lib/api/client';
import { isApiError } from '@/lib/api/errors';
import { formatShortDate } from '@/lib/utils/date';
import type { AdminOrganization, PaginatedResponse } from '@/types/api';

type StatusFilter = 'all' | 'pending_moderation' | 'active' | 'suspended';

const STATUS_LABELS: Record<string, { label: string; variant: 'warning' | 'success' | 'destructive' | 'default' }> = {
  pending_moderation: { label: 'На модерации', variant: 'warning' },
  active: { label: 'Активна', variant: 'success' },
  suspended: { label: 'Заблокирована', variant: 'destructive' },
};

export function OrganizationsTable() {
  const queryClient = useQueryClient();
  const toast = useToast();

  const [statusFilter, setStatusFilter] = useState<StatusFilter>('pending_moderation');
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // Confirmation state
  const [approveId, setApproveId] = useState<string | null>(null);
  const [suspendId, setSuspendId] = useState<string | null>(null);
  const [suspendReason, setSuspendReason] = useState('');

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['admin-organizations', statusFilter],
    queryFn: async () => {
      const params = new URLSearchParams({ per_page: '50' });
      if (statusFilter !== 'all') {
        params.set('status', statusFilter);
      }
      return api<PaginatedResponse<AdminOrganization>>(
        `/api/v1/admin/organizations?${params.toString()}`,
      );
    },
  });

  const approveMutation = useMutation({
    mutationFn: async (id: string) => {
      return api(`/api/v1/admin/organizations/${id}/approve`, { method: 'POST' });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-organizations'] });
      toast.success('Организация одобрена');
    },
    onError: (err) => {
      toast.error(isApiError(err) ? err.message : 'Ошибка при одобрении');
    },
  });

  const suspendMutation = useMutation({
    mutationFn: async ({ id, reason }: { id: string; reason: string }) => {
      return api(`/api/v1/admin/organizations/${id}/suspend`, {
        method: 'POST',
        body: { reason },
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-organizations'] });
      toast.success('Организация заблокирована');
      setSuspendReason('');
    },
    onError: (err) => {
      toast.error(isApiError(err) ? err.message : 'Ошибка при блокировке');
    },
  });

  const orgs = data?.items ?? [];

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-3xl font-semibold tracking-tight">Организации</h1>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Статус:</span>
          <Select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
            className="w-48"
          >
            <option value="all">Все</option>
            <option value="pending_moderation">На модерации</option>
            <option value="active">Активные</option>
            <option value="suspended">Заблокированные</option>
          </Select>
        </div>
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      )}

      {/* Error */}
      {isError && (
        <div className="rounded-lg border border-red-600/30 bg-red-600/10 p-6 text-center">
          <p className="text-red-400">
            {isApiError(error) ? error.message : 'Не удалось загрузить список организаций'}
          </p>
          <Button variant="outline" className="mt-4" onClick={() => refetch()}>
            Повторить
          </Button>
        </div>
      )}

      {/* Empty */}
      {!isLoading && !isError && orgs.length === 0 && (
        <div className="rounded-lg border border-border bg-card p-8 text-center">
          <h3 className="text-lg font-medium">Нет организаций</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            {statusFilter === 'pending_moderation'
              ? 'Нет организаций, ожидающих модерации.'
              : 'Организации с этим статусом отсутствуют.'}
          </p>
        </div>
      )}

      {/* Table */}
      {!isLoading && !isError && orgs.length > 0 && (
        <div className="rounded-lg border border-border overflow-hidden">
          {/* Mobile card view */}
          <div className="md:hidden divide-y divide-border">
            {orgs.map((org) => (
              <div key={org.id} className="p-4 space-y-3">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="font-medium">{org.name}</p>
                    <p className="text-sm text-muted-foreground">{org.slug}.tdpay.ru</p>
                  </div>
                  <Badge variant={STATUS_LABELS[org.status]?.variant ?? 'default'}>
                    {STATUS_LABELS[org.status]?.label ?? org.status}
                  </Badge>
                </div>
                <p className="text-sm text-muted-foreground">{org.owner_email}</p>
                <p className="text-xs text-muted-foreground">{formatShortDate(org.created_at)}</p>
                <div className="flex gap-2">
                  {org.status === 'pending_moderation' && (
                    <Button size="sm" onClick={() => setApproveId(org.id)}>
                      Одобрить
                    </Button>
                  )}
                  {org.status !== 'suspended' && (
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => setSuspendId(org.id)}
                    >
                      Заблокировать
                    </Button>
                  )}
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setExpandedId(expandedId === org.id ? null : org.id)}
                  >
                    {expandedId === org.id ? 'Скрыть' : 'Детали'}
                  </Button>
                </div>
                {expandedId === org.id && (
                  <div className="rounded bg-muted p-3 text-sm space-y-1">
                    <p><strong>ID:</strong> {org.id}</p>
                    <p><strong>Slug:</strong> {org.slug}</p>
                    <p><strong>Email:</strong> {org.owner_email}</p>
                    <p><strong>Создана:</strong> {formatShortDate(org.created_at)}</p>
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Desktop table */}
          <table className="hidden md:table w-full">
            <thead>
              <tr className="border-b border-border bg-muted/50">
                <th className="px-4 py-3 text-left text-sm font-medium">Название</th>
                <th className="px-4 py-3 text-left text-sm font-medium">Slug</th>
                <th className="px-4 py-3 text-left text-sm font-medium">Email владельца</th>
                <th className="px-4 py-3 text-left text-sm font-medium">Статус</th>
                <th className="px-4 py-3 text-left text-sm font-medium">Создана</th>
                <th className="px-4 py-3 text-right text-sm font-medium">Действия</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {orgs.map((org) => (
                <tr key={org.id} className="hover:bg-muted/30 transition-colors">
                  <td className="px-4 py-3 text-sm font-medium">{org.name}</td>
                  <td className="px-4 py-3 text-sm text-muted-foreground font-mono">{org.slug}</td>
                  <td className="px-4 py-3 text-sm">{org.owner_email}</td>
                  <td className="px-4 py-3">
                    <Badge variant={STATUS_LABELS[org.status]?.variant ?? 'default'}>
                      {STATUS_LABELS[org.status]?.label ?? org.status}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-sm text-muted-foreground">
                    {formatShortDate(org.created_at)}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      {org.status === 'pending_moderation' && (
                        <Button size="sm" onClick={() => setApproveId(org.id)}>
                          Одобрить
                        </Button>
                      )}
                      {org.status !== 'suspended' && (
                        <Button
                          size="sm"
                          variant="destructive"
                          onClick={() => setSuspendId(org.id)}
                        >
                          Заблокировать
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setExpandedId(expandedId === org.id ? null : org.id)}
                      >
                        Детали
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Inline details (accordion) */}
          {expandedId && (
            <div className="border-t border-border bg-muted/20 p-4">
              {(() => {
                const org = orgs.find((o) => o.id === expandedId);
                if (!org) return null;
                return (
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm">
                    <div>
                      <p className="text-muted-foreground">ID</p>
                      <p className="font-mono">{org.id}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Slug</p>
                      <p>{org.slug}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Email</p>
                      <p>{org.owner_email}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Статус</p>
                      <Badge variant={STATUS_LABELS[org.status]?.variant}>
                        {STATUS_LABELS[org.status]?.label}
                      </Badge>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Создана</p>
                      <p>{formatShortDate(org.created_at)}</p>
                    </div>
                  </div>
                );
              })()}
            </div>
          )}
        </div>
      )}

      {/* Approve confirm */}
      <ConfirmDialog
        open={!!approveId}
        onOpenChange={(open) => { if (!open) setApproveId(null); }}
        title="Одобрить организацию?"
        description="Организация получит доступ в кабинет и сможет создавать события."
        confirmLabel="Одобрить"
        variant="default"
        onConfirm={() => {
          if (approveId) approveMutation.mutate(approveId);
          setApproveId(null);
        }}
      />

{/* Suspend confirm */}
      <ConfirmDialog
        open={!!suspendId}
        onOpenChange={(open) => { if (!open) { setSuspendId(null); setSuspendReason(''); } }}
        title="Заблокировать организацию?"
        description="Организация потеряет доступ в кабинет. Это действие можно отменить."
        confirmLabel="Заблокировать"
        variant="destructive"
        confirmDisabled={suspendReason.trim() === ''}
        onConfirm={() => {
          if (suspendId && suspendReason.trim()) {
            suspendMutation.mutate({ id: suspendId, reason: suspendReason.trim() });
          }
          setSuspendId(null);
          setSuspendReason('');
        }}
      >
        <div className="space-y-1.5">
          <label htmlFor="suspend-reason" className="text-sm font-medium">
            Причина блокировки
          </label>
          <input
            id="suspend-reason"
            type="text"
            className="flex h-10 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            placeholder="Укажите причину"
            value={suspendReason}
            onChange={(e) => setSuspendReason(e.target.value)}
          />
        </div>
      </ConfirmDialog>
    </div>
  );
}