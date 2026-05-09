'use client';

/**
 * Форма входа в админку.
 * Email + password. Ссылка на magic-link форму.
 * Кнопка Telegram — disabled с tooltip «Скоро».
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
import { useMagicLinkRequest } from '@/lib/auth/use-magic-link';
import { isApiError } from '@/lib/api/errors';
import { loginSchema, magicLinkSchema, type LoginFormData, type MagicLinkFormData } from './schema';

export function LoginForm() {
  const [showMagicLink, setShowMagicLink] = useState(false);
  const [magicLinkSent, setMagicLinkSent] = useState(false);
  const router = useRouter();

  const login = useLogin();
  const magicLink = useMagicLinkRequest();

  const {
    register: reg,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
  });

  const {
    register: regMagic,
    handleSubmit: handleMagicSubmit,
    formState: { errors: magicErrors, isSubmitting: magicSubmitting },
  } = useForm<MagicLinkFormData>({
    resolver: zodResolver(magicLinkSchema),
  });

  const onLogin = async (data: LoginFormData) => {
    try {
      const session = await login.mutateAsync(data);
      // Проверяем роль для platform
      if (session.user?.role === 'superadmin') {
        router.push('/platform');
      } else {
        router.push('/admin');
      }
    } catch (err) {
      if (isApiError(err)) {
        setError('root', { message: err.message });
      } else {
        setError('root', { message: 'Ошибка соединения. Попробуйте позже.' });
      }
    }
  };

  const onMagicLink = async (data: MagicLinkFormData) => {
    try {
      await magicLink.mutateAsync(data);
      setMagicLinkSent(true);
    } catch (err) {
      if (isApiError(err)) {
        setError('root', { message: err.message });
      }
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center px-6">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <h1 className="text-3xl font-semibold">Вход в кабинет</h1>
          <p className="mt-2 text-muted-foreground">
            Войдите для управления организацией
          </p>
        </div>

        {magicLinkSent ? (
          <div className="rounded-lg border border-emerald-600/30 bg-emerald-600/10 p-6 text-center">
            <h2 className="text-lg font-medium text-emerald-400">Письмо отправлено</h2>
            <p className="mt-2 text-sm text-muted-foreground">
              Проверьте почту — мы отправили ссылку для входа.
              Ссылка действительна 15 минут.
            </p>
            <Button
              variant="outline"
              className="mt-4"
              onClick={() => {
                setMagicLinkSent(false);
                setShowMagicLink(false);
              }}
            >
              ← Вернуться ко входу
            </Button>
          </div>
        ) : showMagicLink ? (
          <form
            onSubmit={handleMagicSubmit(onMagicLink)}
            className="rounded-lg border border-border bg-card p-6 space-y-4"
            noValidate
          >
            <h2 className="text-lg font-medium">Вход по ссылке</h2>
            <p className="text-sm text-muted-foreground">
              Введите email — мы отправим ссылку для входа без пароля.
            </p>
            <div className="space-y-1.5">
              <Label htmlFor="magic-email">Email</Label>
              <Input
                id="magic-email"
                type="email"
                autoComplete="email"
                placeholder="you@example.com"
                {...regMagic('email')}
                aria-invalid={!!magicErrors.email}
              />
              {magicErrors.email && (
                <p className="text-sm text-red-400">{magicErrors.email.message}</p>
              )}
            </div>
            <Button type="submit" className="w-full" disabled={magicSubmitting}>
              {magicSubmitting ? (
                <>
                  <Spinner size="sm" /> Отправка...
                </>
              ) : (
                'Отправить ссылку'
              )}
            </Button>
            <Button
              type="button"
              variant="ghost"
              className="w-full"
              onClick={() => setShowMagicLink(false)}
            >
              ← Назад
            </Button>
          </form>
        ) : (
          <form
            onSubmit={handleSubmit(onLogin)}
            className="rounded-lg border border-border bg-card p-6 space-y-4"
            noValidate
          >
            {/* Общая ошибка */}
            {errors.root && (
              <div className="rounded-md border border-red-600/30 bg-red-600/10 px-4 py-3 text-sm text-red-400">
                {errors.root.message}
              </div>
            )}

            <div className="space-y-1.5">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                placeholder="you@example.com"
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

            <div className="space-y-2 pt-2">
              <button
                type="button"
                onClick={() => setShowMagicLink(true)}
                className="w-full text-center text-sm text-primary hover:underline"
              >
                Получить ссылку для входа
              </button>

              <div className="relative">
                <div className="absolute inset-0 flex items-center">
                  <span className="w-full border-t border-border" />
                </div>
                <div className="relative flex justify-center text-xs uppercase">
                  <span className="bg-card px-2 text-muted-foreground">или</span>
                </div>
              </div>

              <Button
                type="button"
                variant="outline"
                className="w-full"
                disabled
                title="Скоро"
              >
                Войти через Telegram
              </Button>
              <p className="text-center text-xs text-muted-foreground">
                Вход через Telegram появится в ближайшем обновлении
              </p>
            </div>
          </form>
        )}
      </div>
    </main>
  );
}