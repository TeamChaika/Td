import { z } from 'zod';

export const brandSchema = z.object({
  brand_name: z.string().max(200, 'Максимум 200 символов').optional().or(z.literal('')),
  brand_color: z
    .string()
    .regex(/^#[0-9a-fA-F]{6}$/, 'Формат: #RRGGBB')
    .optional()
    .or(z.literal('')),
  logo_url: z.string().optional().or(z.literal('')),
});

export type BrandFormData = z.infer<typeof brandSchema>;

export const legalSchema = z.object({
  legal_entity_type: z.enum(['individual', 'sole_proprietor', 'llc', 'self_employed'], {
    errorMap: () => ({ message: 'Выберите тип' }),
  }).optional().or(z.literal('')),
  inn: z
    .string()
    .regex(/^\d{10,12}$/, 'ИНН: 10 или 12 цифр')
    .optional()
    .or(z.literal('')),
  legal_name: z.string().max(500, 'Максимум 500 символов').optional().or(z.literal('')),
  legal_address: z.string().max(500, 'Максимум 500 символов').optional().or(z.literal('')),
});

export type LegalFormData = z.infer<typeof legalSchema>;

export const paymentSchema = z.object({
  qrm_api_login: z.string().max(255).optional().or(z.literal('')),
  qrm_api_key: z.string().max(255).optional().or(z.literal('')),
});

export type PaymentFormData = z.infer<typeof paymentSchema>;

export const contactsSchema = z.object({
  contact_email: z.string().email('Некорректный email').optional().or(z.literal('')),
  contact_phone: z.string().max(20, 'Максимум 20 символов').optional().or(z.literal('')),
  refund_policy: z.string().max(2000).optional().or(z.literal('')),
});

export type ContactsFormData = z.infer<typeof contactsSchema>;

export const telegramSchema = z.object({
  telegram_chat_id: z.string().max(255).optional().or(z.literal('')),
});

export type TelegramFormData = z.infer<typeof telegramSchema>;