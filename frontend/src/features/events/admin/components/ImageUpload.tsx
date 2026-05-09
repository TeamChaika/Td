'use client';

/**
 * ImageUpload — загрузка изображения с drag-n-drop, preview и валидацией.
 * Показывает spinner при загрузке, детальные ошибки от бэкенда.
 */
import { useState, useRef, useCallback, type DragEvent } from 'react';
import { cn } from '@/lib/utils/cn';
import { Button } from '@/components/ui/button';
import { Spinner } from '@/components/ui/spinner';

const MAX_SIZE = 5 * 1024 * 1024; // 5MB
const ALLOWED_TYPES = ['image/webp', 'image/png', 'image/jpeg'];

interface ImageUploadProps {
  currentUrl?: string;
  onFileChange: (file: File | null) => void;
  selectedFile?: File | null;
  label: string;
  hint?: string;
  error?: string;
  /** Флаг загрузки (из родительского mutation) */
  isUploading?: boolean;
  'data-testid'?: string;
}

export function ImageUpload({
  currentUrl,
  onFileChange,
  selectedFile,
  label,
  hint,
  error,
  isUploading,
  'data-testid': testId,
}: ImageUploadProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const previewUrl = selectedFile
    ? URL.createObjectURL(selectedFile)
    : currentUrl ?? null;

  const validateFile = useCallback((file: File): boolean => {
    if (!ALLOWED_TYPES.includes(file.type)) {
      setLocalError('Формат: WebP, PNG или JPEG');
      return false;
    }
    if (file.size > MAX_SIZE) {
      setLocalError('Размер файла не более 5 МБ');
      return false;
    }
    setLocalError(null);
    return true;
  }, []);

  const handleFile = useCallback(
    (file: File | null) => {
      if (!file) {
        onFileChange(null);
        return;
      }
      if (validateFile(file)) {
        onFileChange(file);
      }
    },
    [validateFile, onFileChange],
  );

  const handleDrop = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setIsDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile],
  );

  const handleDragOver = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setIsDragging(false);
  }, []);

  const handleRemove = useCallback(() => {
    onFileChange(null);
    if (inputRef.current) inputRef.current.value = '';
  }, [onFileChange]);

  const displayError = error ?? localError;

  return (
    <div className="space-y-1.5" data-testid={testId}>
      <span className="text-sm font-medium leading-none">{label}</span>
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}

      {previewUrl ? (
        <div className="relative overflow-hidden rounded-lg border border-border">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={previewUrl}
            alt={label}
            className="h-48 w-full object-cover"
          />
          {isUploading && (
            <div className="absolute inset-0 flex items-center justify-center bg-black/40">
              <Spinner size="lg" className="text-white" />
            </div>
          )}
          {!isUploading && (
            <div className="absolute inset-x-0 bottom-0 flex justify-end gap-2 bg-gradient-to-t from-black/60 to-transparent p-3">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => inputRef.current?.click()}
              >
                Заменить
              </Button>
              <Button
                type="button"
                variant="destructive"
                size="sm"
                onClick={handleRemove}
              >
                Удалить
              </Button>
            </div>
          )}
        </div>
      ) : (
        <div
          role="button"
          tabIndex={0}
          onClick={() => inputRef.current?.click()}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') inputRef.current?.click();
          }}
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          className={cn(
            'flex h-48 cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed transition-colors',
            isDragging
              ? 'border-primary bg-primary/10'
              : 'border-border hover:border-muted-foreground/50',
          )}
        >
          {isUploading ? (
            <>
              <Spinner size="lg" className="mb-2" />
              <p className="text-sm text-muted-foreground">Загрузка...</p>
            </>
          ) : (
            <>
              <svg
                className="mb-2 h-8 w-8 text-muted-foreground"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                aria-hidden="true"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
                />
              </svg>
              <p className="text-sm text-muted-foreground">
                Перетащите или нажмите для загрузки
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                WebP, PNG, JPEG до 5 МБ
              </p>
            </>
          )}
        </div>
      )}

      <input
        ref={inputRef}
        type="file"
        accept="image/webp,image/png,image/jpeg"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0] ?? null;
          handleFile(file);
        }}
      />

      {displayError && (
        <p className="text-sm text-red-400">{displayError}</p>
      )}
    </div>
  );
}