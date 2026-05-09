import { z } from 'zod';

export const suspendSchema = z.object({
  reason: z.string().min(1, 'Укажите причину блокировки').max(500, 'Максимум 500 символов'),
});

export type SuspendFormData = z.infer<typeof suspendSchema>;