'use client';

/**
 * Toast / Snackbar компонент.
 * Позиция: bottom-right на десктопе, top на мобильном.
 *
 * Использование:
 * - <ToastProvider> в layout
 * - useToast() → { toast.success(...), toast.error(...), toast.info(...) }
 */
import {
  createContext,
  useCallback,
  useContext,
  useState,
  useRef,
  type ReactNode,
} from 'react';

import { cn } from '@/lib/utils/cn';

type ToastType = 'success' | 'error' | 'info';

interface ToastItem {
  id: number;
  type: ToastType;
  message: string;
}

interface ToastContextValue {
  success: (msg: string) => void;
  error: (msg: string) => void;
  info: (msg: string) => void;
}

const ToastContext = createContext<ToastContextValue>({
  success: () => {},
  error: () => {},
  info: () => {},
});

export function useToast(): ToastContextValue {
  return useContext(ToastContext);
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const nextId = useRef(0);

  const addToast = useCallback((type: ToastType, message: string) => {
    const id = nextId.current++;
    setToasts((prev) => [...prev.slice(-2), { id, type, message }]);
    // Автоудаление для success/info, error остаётся
    if (type !== 'error') {
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
      }, 4000);
    }
  }, []);

  const removeToast = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const value: ToastContextValue = {
    success: (msg) => addToast('success', msg),
    error: (msg) => addToast('error', msg),
    info: (msg) => addToast('info', msg),
  };

  return (
    <ToastContext.Provider value={value}>
      {children}
      {/* Toast container */}
      <div
        aria-live="polite"
        className={cn(
          'fixed z-50 flex flex-col-reverse gap-2',
          // Mobile: top, Desktop: bottom-right
          'inset-x-4 top-4',
          'sm:inset-x-auto sm:bottom-4 sm:right-4 sm:top-auto',
        )}
      >
        {toasts.map((t) => (
          <div
            key={t.id}
            role="alert"
            className={cn(
              'flex items-center gap-3 rounded-lg border px-4 py-3 text-sm shadow-lg transition-all',
              t.type === 'success' &&
                'border-emerald-600/30 bg-emerald-600/10 text-emerald-400',
              t.type === 'error' &&
                'border-red-600/30 bg-red-600/10 text-red-400',
              t.type === 'info' &&
                'border-blue-600/30 bg-blue-600/10 text-blue-400',
            )}
          >
            <span className="flex-1">{t.message}</span>
            <button
              onClick={() => removeToast(t.id)}
              className="shrink-0 rounded p-1 text-current opacity-60 hover:opacity-100"
              aria-label="Закрыть"
            >
              ✕
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}