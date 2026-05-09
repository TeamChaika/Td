import { z } from 'zod';

import { isReservedSlug } from '@/lib/validation/reserved-slugs';

/** Валидация slug: латиница + цифры + дефис, 3..64 символа, не в reserved. */
const slugSchema = z
  .string()
  .min(3, 'Минимум 3 символа')
  .max(64, 'Максимум 64 символа')
  .regex(/^[a-z0-9]+(-[a-z0-9]+)*$/, 'Только латиница, цифры и дефис (не в начале/конце)')
  .refine((s) => !isReservedSlug(s), 'Этот slug зарезервирован');

export const registerSchema = z
  .object({
    email: z
      .string()
      .min(1, 'Email обязателен')
      .email('Некорректный email'),
    password: z
      .string()
      .min(10, 'Минимум 10 символов')
      .regex(/[a-z]/, 'Нужна хотя бы одна строчная буква')
      .regex(/[A-Z]/, 'Нужна хотя бы одна заглавная буква')
      .regex(/[0-9]/, 'Нужна хотя бы одна цифра'),
    password_confirm: z.string().min(1, 'Подтвердите пароль'),
    first_name: z
      .string()
      .min(1, 'Имя обязательно')
      .max(100, 'Максимум 100 символов'),
    last_name: z
      .string()
      .min(1, 'Фамилия обязательна')
      .max(100, 'Максимум 100 символов'),
    organization_name: z
      .string()
      .min(1, 'Название организации обязательно')
      .max(200, 'Максимум 200 символов'),
    organization_slug: slugSchema,
    consent_privacy: z.literal(true, {
      errorMap: () => ({ message: 'Необходимо согласие с политикой конфиденциальности' }),
    }),
    consent_offer: z.literal(true, {
      errorMap: () => ({ message: 'Необходимо согласие с офертой' }),
    }),
  })
  .refine((data) => data.password === data.password_confirm, {
    message: 'Пароли не совпадают',
    path: ['password_confirm'],
  });

export type RegisterFormData = z.infer<typeof registerSchema>;

export const loginSchema = z.object({
  email: z.string().min(1, 'Email обязателен').email('Некорректный email'),
  password: z.string().min(1, 'Пароль обязателен'),
});

export type LoginFormData = z.infer<typeof loginSchema>;

export const magicLinkSchema = z.object({
  email: z.string().min(1, 'Email обязателен').email('Некорректный email'),
});

export type MagicLinkFormData = z.infer<typeof magicLinkSchema>;