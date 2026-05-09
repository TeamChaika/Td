'use client';

/**
 * Страница входа в суперадмин-панель.
 * Такая же форма email+password, но после логина проверяет role === "superadmin".
 */
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useRouter } from 'next/navigation';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Spinner } from '@/components/ui/spinner';
import { useLogin } from '@/lib/auth/use-login';
import { clearSession } from '@/lib/auth/session-store';
import { isApiError } from '@/lib/api/errors';
import { loginSchema, type LoginFormData } from '@/features/auth/schema';

export default function PlatformLoginPage() {
  const router = useRouter();
  const login = useLogin();
  const [error, setError] = useState<string | null>(null);

  const {
    register: reg,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = async (data: LoginFormData) => {
    setError(null);
    try {
      const session = await login.mutateAsync(data);
      if (session.user?.role !== 'superadmin') {
        clearSession();
        setError('Доступ запрещён. Только для суперадминов платформы.');
        return;
      }
      router.push('/platform');
    } catch (err) {
      if (isApiError(err)) {
        setError(err.message);
      } else {
        setError('Ошибка соединения. Попробуйте позже.');
      }
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center px-6">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <h1 className="text-3xl font-semibold">Суперадмин</h1>
          <p className="mt-2 text-muted-foreground">
            Вход в панель управления платформой
          </p>
        </div>

        <form
          onSubmit={handleSubmit(onSubmit)}
          className="rounded-lg border border-border bg-card p-6 space-y-4"
          noValidate
        >
          {error && (
            <div className="rounded-md border border-red-600/30 bg-red-600/10 px-4 py-3 text-sm text-red-400">
              {error}
            </div>
          )}

          <div className="space-y-1.5">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              placeholder="admin@tdpay.ru"
              {...reg('email')}
              aria-invalid={!!errors.email}
            />
            {errors.email && (
              <p className="text-sm text-red-400">{errors.email.message}</p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="password">Пароль</Label>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              placeholder="••••••••"
              {...reg('password')}
              aria-invalid={!!errors.password}
            />
            {errors.password && (
              <p className="text-sm text-red-400">{errors.password.message}</p>
            )}
          </div>

          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting ? (
              <>
                <Spinner size="sm" /> Вход...
              </>
            ) : (
              'Войти'
            )}
          </Button>
        </form>
      </div>
    </main>
  );
}