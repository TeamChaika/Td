'use client';

/**
 * Форма настроек организации с табами:
 * Бренд / Реквизиты / Платежи / Email / Telegram / Контакты
 */
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQueryClient } from '@tanstack/react-query';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { Tabs, type Tab } from '@/components/ui/tabs';
import { Spinner } from '@/components/ui/spinner';
import { useToast } from '@/components/ui/toast';
import { api } from '@/lib/api/client';
import { isApiError } from '@/lib/api/errors';
import type { OrganizationProfile, QrmTestResponse, OrganizationUpdateRequest } from '@/types/api';
import {
  brandSchema,
  legalSchema,
  paymentSchema,
  contactsSchema,
  telegramSchema,
  type BrandFormData,
  type LegalFormData,
  type PaymentFormData,
  type ContactsFormData,
  type TelegramFormData,
} from './schema';

const SETTINGS_TABS: Tab[] = [
  { id: 'brand', label: 'Бренд' },
  { id: 'legal', label: 'Реквизиты' },
  { id: 'payment', label: 'Платежи' },
  { id: 'email', label: 'Email' },
  { id: 'telegram', label: 'Telegram' },
  { id: 'contacts', label: 'Контакты' },
];

interface SettingsFormProps {
  organization: OrganizationProfile;
}

export function SettingsForm({ organization }: SettingsFormProps) {
  const queryClient = useQueryClient();
  const toast = useToast();

  const saveSettings = useMutation({
    mutationFn: async (data: OrganizationUpdateRequest) => {
      // Убираем только undefined (PATCH-семантика: пустая строка — валидное значение,
      // бэк сам решит что с ней делать). Булевы и числовые поля передаём как есть.
      const cleaned: Record<string, unknown> = {};
      for (const [key, value] of Object.entries(data)) {
        if (value !== undefined) {
          cleaned[key] = value;
        }
      }
      return api<OrganizationProfile>('/api/v1/organizer/organization', {
        method: 'PATCH',
        body: cleaned,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['session'] });
      toast.success('Настройки сохранены');
    },
    onError: (err) => {
      if (isApiError(err)) {
        toast.error(err.message);
      } else {
        toast.error('Не удалось сохранить настройки');
      }
    },
  });

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="text-3xl font-semibold tracking-tight mb-8">Настройки</h1>
      <Tabs tabs={SETTINGS_TABS} defaultTab="brand">
        {(activeTab) => {
          switch (activeTab) {
            case 'brand':
              return <BrandTab organization={organization} onSave={(d) => saveSettings.mutateAsync(d)} saving={saveSettings.isPending} />;
            case 'legal':
              return <LegalTab organization={organization} onSave={(d) => saveSettings.mutateAsync(d)} saving={saveSettings.isPending} />;
            case 'payment':
              return <PaymentTab organization={organization} onSave={(d) => saveSettings.mutateAsync(d)} saving={saveSettings.isPending} />;
            case 'email':
              return <EmailTab />;
            case 'telegram':
              return <TelegramTab organization={organization} onSave={(d) => saveSettings.mutateAsync(d)} saving={saveSettings.isPending} />;
            case 'contacts':
              return <ContactsTab organization={organization} onSave={(d) => saveSettings.mutateAsync(d)} saving={saveSettings.isPending} />;
            default:
              return null;
          }
        }}
      </Tabs>
    </div>
  );
}

// ---- Brand Tab ----

function BrandTab({ organization, onSave, saving }: {
  organization: OrganizationProfile;
  onSave: (d: OrganizationUpdateRequest) => Promise<unknown>;
  saving: boolean;
}) {
  const { register, handleSubmit, formState: { errors } } = useForm<BrandFormData>({
    resolver: zodResolver(brandSchema),
    defaultValues: {
      brand_name: organization.brand_name ?? '',
      brand_color: organization.brand_color ?? '',
      logo_url: '',
    },
  });

  return (
    <form
      onSubmit={handleSubmit((d) =>
        onSave({
          brand_name: d.brand_name || null,
          brand_color: d.brand_color || null,
          logo_url: d.logo_url || undefined,
        }),
      )}
      className="space-y-4"
    >
      <div className="space-y-1.5">
        <Label htmlFor="brand_logo">Логотип</Label>
        <div className="flex items-center gap-4">
          {organization.logo_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={organization.logo_url} alt="Logo" className="h-16 w-16 rounded object-contain bg-muted" />
          ) : (
            <div className="h-16 w-16 rounded bg-muted flex items-center justify-center text-muted-foreground text-xs">
              Нет
            </div>
          )}
          <div className="flex-1">
            <p className="text-sm text-muted-foreground mb-2">
              Загрузка логотипа появится в одном из следующих обновлений.
            </p>
            {/* Upload появится с S3-интеграцией в отдельной фазе */}
          </div>
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="brand_name">Название бренда</Label>
        <Input id="brand_name" placeholder="Моя компания" {...register('brand_name')} />
        {errors.brand_name && <p className="text-sm text-red-400">{errors.brand_name.message}</p>}
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="brand_color">Цвет бренда</Label>
        <div className="flex items-center gap-3">
          <input
            type="color"
            id="brand_color"
            className="h-10 w-10 rounded border border-border bg-transparent cursor-pointer"
            {...register('brand_color')}
          />
          <Input
            className="flex-1"
            placeholder="#3B82F6"
            {...register('brand_color')}
          />
        </div>
        {errors.brand_color && <p className="text-sm text-red-400">{errors.brand_color.message}</p>}
      </div>

      <Button type="submit" disabled={saving}>
        {saving ? <><Spinner size="sm" /> Сохранение...</> : 'Сохранить'}
      </Button>
    </form>
  );
}

// ---- Legal Tab ----

function LegalTab({ organization, onSave, saving }: {
  organization: OrganizationProfile;
  onSave: (d: OrganizationUpdateRequest) => Promise<unknown>;
  saving: boolean;
}) {
  const { register, handleSubmit, formState: { errors } } = useForm<LegalFormData>({
    resolver: zodResolver(legalSchema),
    defaultValues: {
      legal_entity_type: organization.legal_entity_type as LegalFormData['legal_entity_type'] ?? '',
      inn: organization.legal_inn ?? '',
      legal_name: organization.legal_name ?? '',
      legal_address: organization.legal_address ?? '',
    },
  });

  const onSubmit = (d: LegalFormData) => {
    // Маппим поле формы inn → legal_inn (бэкенд)
    const payload: OrganizationUpdateRequest = {
      legal_entity_type: d.legal_entity_type || null,
      legal_inn: d.inn || null,
      legal_name: d.legal_name || null,
      legal_address: d.legal_address || null,
    };
    return onSave(payload);
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      <div className="space-y-1.5">
        <Label htmlFor="legal_entity_type">Тип юрлица</Label>
        <Select id="legal_entity_type" {...register('legal_entity_type')}>
          <option value="">Не выбрано</option>
          <option value="individual">Физическое лицо</option>
          <option value="sole_proprietor">ИП</option>
          <option value="llc">ООО</option>
          <option value="self_employed">Самозанятый</option>
        </Select>
        {errors.legal_entity_type && <p className="text-sm text-red-400">{errors.legal_entity_type.message}</p>}
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="inn">ИНН</Label>
        <Input id="inn" placeholder="1234567890" {...register('inn')} />
        {errors.inn && <p className="text-sm text-red-400">{errors.inn.message}</p>}
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="legal_name">Юридическое название</Label>
        <Input id="legal_name" placeholder='ООО "Моя компания"' {...register('legal_name')} />
        {errors.legal_name && <p className="text-sm text-red-400">{errors.legal_name.message}</p>}
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="legal_address">Юридический адрес</Label>
        <Input id="legal_address" placeholder="г. Москва, ул. Примерная, д. 1" {...register('legal_address')} />
        {errors.legal_address && <p className="text-sm text-red-400">{errors.legal_address.message}</p>}
      </div>

      <Button type="submit" disabled={saving}>
        {saving ? <><Spinner size="sm" /> Сохранение...</> : 'Сохранить'}
      </Button>
    </form>
  );
}

// ---- Payment Tab ----

function PaymentTab({ organization, onSave, saving }: {
  organization: OrganizationProfile;
  onSave: (d: OrganizationUpdateRequest) => Promise<unknown>;
  saving: boolean;
}) {
  const [showKey, setShowKey] = useState(false);
  const [testResult, setTestResult] = useState<QrmTestResponse | null>(null);
  const [testing, setTesting] = useState(false);
  const toast = useToast();

  const { register, handleSubmit, watch, formState: { errors } } = useForm<PaymentFormData>({
    resolver: zodResolver(paymentSchema),
    defaultValues: {
      qrm_api_login: organization.qrm_api_login ?? '',
      qrm_api_key: '',
    },
  });

  const qrmApiKey = watch('qrm_api_key');

  const testKey = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      // Если пользователь ввёл ключ — тестируем его; иначе бэк использует сохранённый
      const body: Record<string, string | undefined> = {};
      if (qrmApiKey && qrmApiKey.trim()) {
        body.qrm_api_key = qrmApiKey.trim();
      }
      const res = await api<QrmTestResponse>('/api/v1/organizer/organization/qrm/test', {
        method: 'POST',
        body: Object.keys(body).length > 0 ? body : undefined,
      });
      setTestResult(res);
      if (res.ok) {
        toast.success('Ключ работает');
      } else {
        toast.error(res.message);
      }
    } catch (err) {
      if (isApiError(err)) {
        toast.error(err.message);
      } else {
        toast.error('Не удалось проверить ключ');
      }
    } finally {
      setTesting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit((d) => onSave(d))} className="space-y-4">
      <div className="space-y-1.5">
        <Label htmlFor="qrm_api_login">QRM Логин</Label>
        <Input
          id="qrm_api_login"
          placeholder={organization.qrm_api_login ? '••••••' : 'Логин от QRM'}
          {...register('qrm_api_login')}
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="qrm_api_key">QRM API Ключ</Label>
        <div className="flex gap-2">
          <Input
            id="qrm_api_key"
            type={showKey ? 'text' : 'password'}
            placeholder={organization.qrm_api_key_masked ? organization.qrm_api_key_masked : 'API ключ от QRM'}
            {...register('qrm_api_key')}
          />
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setShowKey(!showKey)}
          >
            {showKey ? 'Скрыть' : 'Показать'}
          </Button>
        </div>
        {errors.qrm_api_key && <p className="text-sm text-red-400">{errors.qrm_api_key.message}</p>}
      </div>

      <div className="flex gap-3">
        <Button type="submit" disabled={saving}>
          {saving ? <><Spinner size="sm" /> Сохранение...</> : 'Сохранить'}
        </Button>
        <Button
          type="button"
          variant="outline"
          onClick={testKey}
          disabled={testing}
        >
          {testing ? <><Spinner size="sm" /> Проверка...</> : 'Проверить ключ'}
        </Button>
      </div>

      {testResult && (
        <div className={`rounded-md border px-4 py-3 text-sm ${testResult.ok ? 'border-emerald-600/30 bg-emerald-600/10 text-emerald-400' : 'border-red-600/30 bg-red-600/10 text-red-400'}`}>
          {testResult.message}
        </div>
      )}
    </form>
  );
}

// ---- Email Tab (заглушка) ----

function EmailTab() {
  return (
    <div className="rounded-lg border border-border bg-card p-6 text-center">
      <h3 className="text-lg font-medium">Кастомный SMTP</h3>
      <p className="mt-2 text-sm text-muted-foreground">
        Настройка собственного SMTP-сервера для отправки писем появится в ближайшем обновлении.
        Пока все письма отправляются с почтового сервера платформы.
      </p>
    </div>
  );
}

// ---- Telegram Tab ----

function TelegramTab({ organization, onSave, saving }: {
  organization: OrganizationProfile;
  onSave: (d: OrganizationUpdateRequest) => Promise<unknown>;
  saving: boolean;
}) {
  const { register, handleSubmit, formState: { errors } } = useForm<TelegramFormData>({
    resolver: zodResolver(telegramSchema),
    defaultValues: {
      telegram_chat_id: organization.telegram_chat_id !== null ? String(organization.telegram_chat_id) : '',
    },
  });

  const onSubmit = (d: TelegramFormData) => {
    // Конвертируем строку в number для бэкенда (telegram_chat_id: int | None)
    const payload: OrganizationUpdateRequest = {
      telegram_chat_id: d.telegram_chat_id && d.telegram_chat_id.trim()
        ? Number(d.telegram_chat_id)
        : null,
    };
    return onSave(payload);
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      <div className="rounded-lg border border-border bg-card p-4 text-sm text-muted-foreground space-y-1">
        <p>1. Добавьте бота <strong>@TDPayBot</strong> в ваш Telegram-чат</p>
        <p>2. Отправьте в чат команду <code className="bg-muted px-1 rounded">/id</code></p>
        <p>3. Бот ответит ID чата — скопируйте его в поле ниже</p>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="telegram_chat_id">Telegram Chat ID</Label>
        <Input id="telegram_chat_id" placeholder="-1001234567890" {...register('telegram_chat_id')} />
        {errors.telegram_chat_id && <p className="text-sm text-red-400">{errors.telegram_chat_id.message}</p>}
      </div>

      <Button type="submit" disabled={saving}>
        {saving ? <><Spinner size="sm" /> Сохранение...</> : 'Сохранить'}
      </Button>
    </form>
  );
}

// ---- Contacts Tab ----

function ContactsTab({ organization, onSave, saving }: {
  organization: OrganizationProfile;
  onSave: (d: OrganizationUpdateRequest) => Promise<unknown>;
  saving: boolean;
}) {
  const { register, handleSubmit, formState: { errors } } = useForm<ContactsFormData>({
    resolver: zodResolver(contactsSchema),
    defaultValues: {
      contact_email: organization.contact_email ?? '',
      contact_phone: organization.contact_phone ?? '',
      refund_policy: organization.refund_policy ?? '',
    },
  });

  return (
    <form onSubmit={handleSubmit((d) => onSave(d))} className="space-y-4">
      <div className="space-y-1.5">
        <Label htmlFor="contact_email">Контактный email</Label>
        <Input id="contact_email" type="email" placeholder="info@example.com" {...register('contact_email')} />
        {errors.contact_email && <p className="text-sm text-red-400">{errors.contact_email.message}</p>}
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="contact_phone">Контактный телефон</Label>
        <Input id="contact_phone" type="tel" placeholder="+7 999 123-45-67" {...register('contact_phone')} />
        {errors.contact_phone && <p className="text-sm text-red-400">{errors.contact_phone.message}</p>}
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="refund_policy">Политика возвратов</Label>
        <Textarea
          id="refund_policy"
          rows={4}
          placeholder="Опишите условия возврата билетов..."
          {...register('refund_policy')}
        />
        {errors.refund_policy && <p className="text-sm text-red-400">{errors.refund_policy.message}</p>}
      </div>

      <Button type="submit" disabled={saving}>
        {saving ? <><Spinner size="sm" /> Сохранение...</> : 'Сохранить'}
      </Button>
    </form>
  );
}