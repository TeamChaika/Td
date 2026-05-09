import { z } from 'zod';
import { isReservedSlug } from '@/lib/validation/reserved-slugs';

// ---- Slug ----

const slugField = z
  .string()
  .min(1, 'Slug обязателен')
  .max(64, 'Максимум 64 символа')
  .regex(
    /^[a-z0-9]+(-[a-z0-9]+)*$/,
    'Только латиница, цифры и дефис (не в начале/конце)',
  )
  .refine((s) => !isReservedSlug(s), 'Этот slug зарезервирован');

// ---- Schedule (backend: ScheduleSingle | ScheduleSessions | SchedulePeriod) ----

const dateTimeString = z.string().min(1, 'Дата обязательна');

const scheduleSingleBase = z.object({
  type: z.literal('single'),
  starts_at: dateTimeString,
  ends_at: dateTimeString, // required в backend
});

const scheduleSessionsBase = z.object({
  type: z.literal('sessions'),
  sessions: z
    .array(
      z.object({
        id: z.string().min(1, 'ID обязателен'),
        starts_at: dateTimeString,
        ends_at: dateTimeString, // required в backend
      }),
    )
    .min(1, 'Добавьте хотя бы один сеанс')
    .max(100, 'Максимум 100 сеансов'),
});

const schedulePeriodBase = z.object({
  type: z.literal('period'),
  starts_at: dateTimeString,
  ends_at: dateTimeString, // required в backend
  description: z
    .string()
    .max(2000, 'Максимум 2000 символов')
    .optional()
    .or(z.literal('')),
});

export const scheduleSchema = z
  .discriminatedUnion('type', [
    scheduleSingleBase,
    scheduleSessionsBase,
    schedulePeriodBase,
  ])
  .refine(
    (d) => {
      if (d.type === 'single' || d.type === 'period') {
        return new Date(d.ends_at) > new Date(d.starts_at);
      }
      if (d.type === 'sessions') {
        return d.sessions.every(
          (s) => new Date(s.ends_at) > new Date(s.starts_at),
        );
      }
      return true;
    },
    { message: 'Дата окончания должна быть позже начала' },
  )
  .refine(
    (d) => {
      if (d.type === 'single' || d.type === 'period') {
        return new Date(d.starts_at) >= new Date(Date.now() - 86400000);
      }
      if (d.type === 'sessions') {
        return d.sessions.every(
          (s) => new Date(s.starts_at) >= new Date(Date.now() - 86400000),
        );
      }
      return true;
    },
    { message: 'Дата начала не может быть в прошлом' },
  );

export type ScheduleFormData = z.infer<typeof scheduleSchema>;

// ---- Capacity Policy (backend: total={limit}, hybrid={total}, per_tariff, unlimited) ----

const capacityTotal = z.object({
  type: z.literal('total'),
  limit: z
    .number({ required_error: 'Укажите общий лимит' })
    .int('Должно быть целым числом')
    .min(1, 'Минимум 1 место'),
});

const capacityPerTariff = z.object({
  type: z.literal('per_tariff'),
});

const capacityHybrid = z.object({
  type: z.literal('hybrid'),
  total: z
    .number({ required_error: 'Укажите общий лимит' })
    .int('Должно быть целым числом')
    .min(1, 'Минимум 1 место'),
});

const capacityUnlimited = z.object({
  type: z.literal('unlimited'),
});

export const capacityPolicySchema = z.discriminatedUnion('type', [
  capacityTotal,
  capacityPerTariff,
  capacityHybrid,
  capacityUnlimited,
]);

export type CapacityPolicyFormData = z.infer<typeof capacityPolicySchema>;

// ---- Custom Field (backend: text|textarea|number|select|multiselect|checkbox|date) ----

export const customFieldTypeSchema = z.enum([
  'text',
  'textarea',
  'number',
  'select',
  'multiselect',
  'checkbox',
  'date',
]);

export const customFieldSchema = z
  .object({
    id: z
      .string()
      .min(1, 'ID обязателен')
      .max(64, 'Максимум 64 символа')
      .regex(/^[a-z0-9_]+$/, 'Только латиница, цифры и подчёркивание'),
    label: z
      .string()
      .min(1, 'Название обязательно')
      .max(200, 'Максимум 200 символов'),
    type: customFieldTypeSchema,
    required: z.boolean(),
    options: z
      .array(z.string().min(1, 'Опция не может быть пустой'))
      .optional(),
    max_length: z
      .number()
      .int()
      .min(1)
      .max(10000)
      .optional()
      .nullable(),
  })
  .refine(
    (d) => {
      if (d.type === 'select' || d.type === 'multiselect') {
        return d.options !== undefined && d.options.length >= 1;
      }
      return true;
    },
    {
      message: 'Для select/multiselect нужен непустой список опций',
      path: ['options'],
    },
  );

export const customFieldsSchema = z
  .array(customFieldSchema)
  .max(10, 'Максимум 10 полей')
  .refine(
    (fields) => {
      const ids = fields.map((f) => f.id);
      return new Set(ids).size === ids.length;
    },
    { message: 'ID полей должны быть уникальными' },
  );

export type CustomFieldFormData = z.infer<typeof customFieldSchema>;

// ---- Tariff ----

export const tariffSchema = z.object({
  /** id на бэкенде (null для новых тарифов) */
  backendId: z.string().optional(),
  name: z
    .string()
    .min(1, 'Название обязательно')
    .max(200, 'Максимум 200 символов'),
  description: z
    .string()
    .max(500, 'Максимум 500 символов')
    .optional()
    .or(z.literal('')),
  price_rub: z
    .number({ required_error: 'Укажите цену' })
    .min(0, 'Цена не может быть отрицательной')
    .max(10000000, 'Максимум 10 млн ₽'),
  capacity_limit: z
    .number()
    .int('Должно быть целым числом')
    .min(0, 'Не может быть отрицательным')
    .optional()
    .nullable(),
  is_active: z.boolean(),
  /** Порядок сортировки (backend: sort_order) */
  sort_order: z.number().int().min(0).optional().default(0),
});

export type TariffFormData = z.infer<typeof tariffSchema>;

// ---- Full wizard form ----

export const eventWizardSchema = z
  .object({
    title: z
      .string()
      .min(1, 'Название обязательно')
      .max(200, 'Максимум 200 символов'),
    slug: slugField,
    description_md: z
      .string()
      .max(10000, 'Максимум 10 000 символов')
      .optional()
      .or(z.literal('')),
    location_name: z
      .string()
      .min(1, 'Место обязательно')
      .max(200, 'Максимум 200 символов'),
    location_address: z
      .string()
      .max(500, 'Максимум 500 символов')
      .optional()
      .or(z.literal('')),
    schedule: scheduleSchema,
    capacity_policy: capacityPolicySchema,
    tariffs: z.array(tariffSchema).min(1, 'Добавьте хотя бы один тариф'),
    custom_fields: customFieldsSchema.optional().default([]),
  })
  .refine(
    (data) => {
      if (
        data.capacity_policy.type === 'per_tariff' ||
        data.capacity_policy.type === 'hybrid'
      ) {
        return data.tariffs.every(
          (t) =>
            t.capacity_limit !== null &&
            t.capacity_limit !== undefined &&
            t.capacity_limit >= 1,
        );
      }
      return true;
    },
    {
      message:
        'При политике "Лимит на тариф" или "Гибрид" каждый тариф должен иметь лимит мест',
      path: ['tariffs'],
    },
  );

export type EventWizardFormData = z.infer<typeof eventWizardSchema>;

// ---- Per-step schemas ----

const eventWizardBase = z.object({
  title: z
    .string()
    .min(1, 'Название обязательно')
    .max(200, 'Максимум 200 символов'),
  slug: slugField,
  description_md: z
    .string()
    .max(10000, 'Максимум 10 000 символов')
    .optional()
    .or(z.literal('')),
  location_name: z
    .string()
    .min(1, 'Место обязательно')
    .max(200, 'Максимум 200 символов'),
  location_address: z
    .string()
    .max(500, 'Максимум 500 символов')
    .optional()
    .or(z.literal('')),
  schedule: scheduleSchema,
  capacity_policy: capacityPolicySchema,
  tariffs: z.array(tariffSchema).min(1, 'Добавьте хотя бы один тариф'),
  custom_fields: customFieldsSchema.optional().default([]),
});

export const step1Schema = eventWizardBase.pick({
  title: true,
  slug: true,
  description_md: true,
  location_name: true,
  location_address: true,
  schedule: true,
});

export type Step1FormData = z.infer<typeof step1Schema>;

export const step2Schema = eventWizardBase.pick({
  capacity_policy: true,
  tariffs: true,
});

export type Step2FormData = z.infer<typeof step2Schema>;

export const step3Schema = eventWizardBase.pick({
  custom_fields: true,
});

export type Step3FormData = z.infer<typeof step3Schema>;

// ---- Helpers ----

/** Превратить заголовок в slug: транслитерация + латиница/цифры/дефис. */
export function slugify(text: string): string {
  const ru: Record<string, string> = {
    а: 'a', б: 'b', в: 'v', г: 'g', д: 'd', е: 'e', ё: 'yo',
    ж: 'zh', з: 'z', и: 'i', й: 'y', к: 'k', л: 'l', м: 'm',
    н: 'n', о: 'o', п: 'p', р: 'r', с: 's', т: 't', у: 'u',
    ф: 'f', х: 'kh', ц: 'ts', ч: 'ch', ш: 'sh', щ: 'shch',
    ъ: '', ы: 'y', ь: '', э: 'e', ю: 'yu', я: 'ya',
  };
  let slug = text
    .toLowerCase()
    .split('')
    .map((c) => ru[c] ?? c)
    .join('')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
  if (slug.length > 64) slug = slug.slice(0, 64).replace(/-+$/, '');
  if (slug.length < 3) slug = slug.padEnd(3, '0');
  return slug;
}

/** Генератор коротких UUID для session id на клиенте. */
export function generateSessionId(): string {
  return crypto.randomUUID();
}
