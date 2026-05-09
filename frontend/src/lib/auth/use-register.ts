'use client';

/**
 * useRegister — мутация для регистрации организатора.
 * Трансформирует данные формы (RegisterFormData) в payload бэкенда
 * (OrganizationRegisterRequest): два чекбокса → одно поле accept_terms.
 */
import { useMutation } from '@tanstack/react-query';

import { api } from '@/lib/api/client';
import type { RegisterRequest, RegisterResponse } from '@/types/api';
import type { RegisterFormData } from '@/features/auth/schema';

export function useRegister() {
  return useMutation({
    mutationFn: async (data: RegisterFormData) => {
      const payload: RegisterRequest = {
        email: data.email,
        password: data.password,
        first_name: data.first_name,
        last_name: data.last_name,
        organization_name: data.organization_name,
        organization_slug: data.organization_slug,
        accept_terms: data.consent_privacy && data.consent_offer,
      };
      return api<RegisterResponse>('/api/v1/public/organizations/register', {
        method: 'POST',
        body: payload,
      });
    },
  });
}