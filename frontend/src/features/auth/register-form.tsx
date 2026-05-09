'use client';

/**
 * Форма регистрации организатора.
 * Поля: email, password + confirm, first_name, last_name,
 * organization_name, organization_slug (live-check), consent checkboxes.
 */
import { useState, useCallback, useRef, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import Link from 'next/link';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { Spinner } from '@/components/ui/spinner';
import { useRegister } from '@/lib/auth/use-register';
import { api } from '@/lib/api/client';
import { isApiError } from '@/lib/api/errors';
import { cn } from '@/lib/utils/cn';
import { registerSchema, type RegisterFormData } from './schema';

/** Определить почтовый сервис по домену email. */
function detectEmailProvider(email: string): { name: string; url: string } | null {
  const domain = email.split('@')[1]?.toLowerCase();
  if (!domain) return null;
  const providers: Record<string, { name: string; url: string }> = {
    'gmail.com': { name: 'Gmail', url: 'https://mail.google.com' },
    'googlemail.com': { name: 'Gmail', url: 'https://mail.google.com' },
    'yandex.ru': { name: 'Яндекс.Почта', url: 'https://mail.yandex.ru' },
    'yandex.com': { name: 'Яндекс.Почта', url: 'https://mail.yandex.ru' },
    'mail.ru': { name: 'Mail.ru', url: 'https://mail.ru' },
    'inbox.ru': { name: 'Mail.ru', url: 'https://mail.ru' },
    'list.ru': { name: 'Mail.ru', url: 'https://mail.ru' },
    'bk.ru': { name: 'Mail.ru', url: 'https://mail.ru' },
    'outlook.com': { name: 'Outlook', url: 'https://outlook.live.com' },
    'hotmail.com': { name: 'Outlook', url: 'https://outlook.live.com' },
    'icloud.com': { name: 'iCloud', url: 'https://www.icloud.com/mail' },
    'protonmail.com': { name: 'ProtonMail', url: 'https://mail.proton.me' },
    'proton.me': { name: 'ProtonMail', url: 'https://mail.proton.me' },
  };
  return providers[domain] ?? null;
}

/** Оценка надёжности пароля: 0-4. */
function passwordStrength(password: string): { score: number; label: string; color: string } {
  let score = 0;
  if (password.length >= 10) score++;
  if (password.length >= 14) score++;
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score++;
  if (/[0-9]/.test(password)) score++;
  if (/[^a-zA-Z0-9]/.test(password)) score++;

  const labels = ['Очень слабый', 'Слабый', 'Средний', 'Хороший', 'Отличный'];
  const colors = ['bg-red-500', 'bg-orange-500', 'bg-yellow-500', 'bg-emerald-500', 'bg-emerald-600'];

  return {
    score: Math.min(score, 4),
    label: labels[Math.min(score, 4)] ?? 'Очень слабый',
    color: colors[Math.min(score, 4)] ?? 'bg-red-500',
  };
}

export function RegisterForm() {
  const [success, setSuccess] = useState(false);
  const [registeredEmail, setRegisteredEmail] = useState('');
  const [slugStatus, setSlugStatus] = useState<'idle' | 'checking' | 'available' | 'taken'>('idle');
  const [slugMessage, setSlugMessage] = useState('');
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const register = useRegister();

  const {
    register: reg,
    handleSubmit,
    watch,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<RegisterFormData>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      email: '',
      password: '',
      password_confirm: '',
      first_name: '',
      last_name: '',
      organization_name: '',
      organization_slug: '',
      consent_privacy: false as unknown as true,
      consent_offer: false as unknown as true,
    },
  });

  const password = watch('password');
  const slug = watch('organization_slug');
  const strength = passwordStrength(password ?? '');

  // Live slug check
  const checkSlug = useCallback(async (value: string) => {
    if (value.length < 3) {
      setSlugStatus('idle');
      setSlugMessage('');
      return;
    }
    setSlugStatus('checking');
    try {
      const data = await api<{ available: boolean; reason: string | null }>(
        `/api/v1/public/organizations/slug-check?slug=${encodeURIComponent(value)}`,
      );
      if (data.available) {
        setSlugStatus('available');
        setSlugMessage('Доступен');
      } else {
        setSlugStatus('taken');
        const reasonMessages: Record<string, string> = {
          taken: 'Этот slug уже занят',
          reserved: 'Этот slug зарезервирован',
          invalid_format: 'Некорректный формат slug',
        };
        setSlugMessage(reasonMessages[data.reason ?? 'taken'] ?? 'Недоступен');
      }
    } catch {
      // На ошибку сети показываем нейтрально
      setSlugStatus('idle');
      setSlugMessage('');
    }
  }, []);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!slug || slug.length < 3) {
      setSlugStatus('idle');
      setSlugMessage('');
      return;
    }
    debounceRef.current = setTimeout(() => {
      checkSlug(slug);
    }, 400);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [slug, checkSlug]);

  const onSubmit = async (data: RegisterFormData) => {
    try {
      await register.mutateAsync(data);
      setRegisteredEmail(data.email);
      setSuccess(true);
    } catch (err) {
      if (isApiError(err)) {
        if (err.details?.field) {
          setError(err.details.field as keyof RegisterFormData, {
            message: err.message,
          });
        } else {
          setError('root', { message: err.message });
        }
      } else {
        setError('root', { message: 'Произошла ошибка. Попробуйте позже.' });
      }
    }
  };

  if (success) {
    const provider = detectEmailProvider(registeredEmail);
    return (
      <main className="mx-auto max-w-lg px-6 py-16 text-center">
        <div className="rounded-lg border border-emerald-600/30 bg-emerald-600/10 p-8">
          <h1 className="text-2xl font-semibold text-emerald-400">
            Заявка отправлена на модерацию
          </h1>
          <p className="mt-4 text-muted-foreground">
            Мы проверим ваши данные и свяжемся с вами в ближайшее время.
            Обычно это занимает до 24 часов.
          </p>
          {provider ? (
            <Button asChild className="mt-6">
              <a href={provider.url} target="_blank" rel="noopener noreferrer">
                Открыть {provider.name}
              </a>
            </Button>
          ) : (
            <p className="mt-6 text-sm text-muted-foreground">
              Проверьте почту {registeredEmail} — мы отправили письмо с подтверждением.
            </p>
          )}
          <Button asChild variant="outline" className="mt-4">
            <Link href="/">← На главную</Link>
          </Button>
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-lg px-6 py-10">
      <div className="mb-8 text-center">
        <h1 className="text-3xl font-semibold">Регистрация организатора</h1>
        <p className="mt-2 text-muted-foreground">
          Создайте организацию и начните продавать билеты
        </p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-5" noValidate>
        {/* Общая ошибка */}
        {errors.root && (
          <div className="rounded-md border border-red-600/30 bg-red-600/10 px-4 py-3 text-sm text-red-400">
            {errors.root.message}
          </div>
        )}

        {/* Email */}
        <div className="space-y-1.5">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            placeholder="you@example.com"
            data-testid="register-email"
            {...reg('email')}
            aria-invalid={!!errors.email}
          />
          {errors.email && (
            <p className="text-sm text-red-400">{errors.email.message}</p>
          )}
        </div>

        {/* Password */}
        <div className="space-y-1.5">
          <Label htmlFor="password">Пароль</Label>
          <Input
            id="password"
            type="password"
            autoComplete="new-password"
            placeholder="Минимум 10 символов"
            data-testid="register-password"
            {...reg('password')}
            aria-invalid={!!errors.password}
          />
          {password && (
            <div className="mt-1 space-y-1">
              <div className="flex gap-1">
                {[0, 1, 2, 3, 4].map((i) => (
                  <div
                    key={i}
                    className={cn(
                      'h-1 flex-1 rounded-full',
                      i <= strength.score ? strength.color : 'bg-muted',
                    )}
                  />
                ))}
              </div>
              <p className="text-xs text-muted-foreground">{strength.label}</p>
            </div>
          )}
          {errors.password && (
            <p className="text-sm text-red-400">{errors.password.message}</p>
          )}
        </div>

        {/* Password confirm */}
        <div className="space-y-1.5">
          <Label htmlFor="password_confirm">Подтверждение пароля</Label>
          <Input
            id="password_confirm"
            type="password"
            autoComplete="new-password"
            placeholder="Повторите пароль"
            data-testid="register-password-confirm"
            {...reg('password_confirm')}
            aria-invalid={!!errors.password_confirm}
          />
          {errors.password_confirm && (
            <p className="text-sm text-red-400">{errors.password_confirm.message}</p>
          )}
        </div>

        {/* Name fields */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="first_name">Имя</Label>
            <Input
              id="first_name"
              autoComplete="given-name"
              placeholder="Иван"
              data-testid="register-first-name"
              {...reg('first_name')}
              aria-invalid={!!errors.first_name}
            />
            {errors.first_name && (
              <p className="text-sm text-red-400">{errors.first_name.message}</p>
            )}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="last_name">Фамилия</Label>
            <Input
              id="last_name"
              autoComplete="family-name"
              placeholder="Иванов"
              data-testid="register-last-name"
              {...reg('last_name')}
              aria-invalid={!!errors.last_name}
            />
            {errors.last_name && (
              <p className="text-sm text-red-400">{errors.last_name.message}</p>
            )}
          </div>
        </div>

        {/* Organization name */}
        <div className="space-y-1.5">
          <Label htmlFor="organization_name">Название организации</Label>
          <Input
            id="organization_name"
            placeholder="Моя организация"
            data-testid="register-org-name"
            {...reg('organization_name')}
            aria-invalid={!!errors.organization_name}
          />
          {errors.organization_name && (
            <p className="text-sm text-red-400">{errors.organization_name.message}</p>
          )}
        </div>

        {/* Organization slug */}
        <div className="space-y-1.5">
          <Label htmlFor="organization_slug">Поддомен</Label>
          <div className="flex items-center gap-2">
            <Input
              id="organization_slug"
              placeholder="my-org"
              className="flex-1"
              data-testid="register-org-slug"
              {...reg('organization_slug')}
              aria-invalid={!!errors.organization_slug}
            />
            <span className="shrink-0 text-sm text-muted-foreground">
              .tdpay.ru
            </span>
          </div>
          {slugStatus === 'checking' && (
            <p className="text-sm text-muted-foreground">Проверяем...</p>
          )}
          {slugStatus === 'available' && (
            <p className="text-sm text-emerald-400">{slugMessage || 'Доступен'}</p>
          )}
          {slugStatus === 'taken' && (
            <p className="text-sm text-red-400">{slugMessage}</p>
          )}
          {errors.organization_slug && (
            <p className="text-sm text-red-400">{errors.organization_slug.message}</p>
          )}
        </div>

        {/* Consents */}
        <div className="space-y-3">
          <Checkbox
            label={
              <span>
                Я согласен с{' '}
                <Link href="/privacy" className="text-primary underline" target="_blank">
                  политикой конфиденциальности
                </Link>
              </span>
            }
            data-testid="register-consent-privacy"
            {...reg('consent_privacy')}
          />
          {errors.consent_privacy && (
            <p className="text-sm text-red-400">{errors.consent_privacy.message}</p>
          )}
          <Checkbox
            label={
              <span>
                Я согласен с{' '}
                <Link href="/terms" className="text-primary underline" target="_blank">
                  публичной офертой
                </Link>
              </span>
            }
            data-testid="register-consent-offer"
            {...reg('consent_offer')}
          />
          {errors.consent_offer && (
            <p className="text-sm text-red-400">{errors.consent_offer.message}</p>
          )}
        </div>

        <Button type="submit" className="w-full" disabled={isSubmitting} data-testid="register-submit">
          {isSubmitting ? (
            <>
              <Spinner size="sm" /> Отправка...
            </>
          ) : (
            'Зарегистрироваться'
          )}
        </Button>

        <p className="text-center text-sm text-muted-foreground">
          Уже есть аккаунт?{' '}
          <Link href="/admin/login" className="text-primary underline">
            Войти
          </Link>
        </p>
      </form>
    </main>
  );
}