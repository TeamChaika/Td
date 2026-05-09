'use client';

/**
 * Checkbox — стилизованный чекбокс.
 */
import * as React from 'react';

import { cn } from '@/lib/utils/cn';

interface CheckboxProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label?: React.ReactNode;
}

const Checkbox = React.forwardRef<HTMLInputElement, CheckboxProps>(
  ({ className, label, id, ...props }, ref) => {
    const checkboxId = id ?? props.name;
    return (
      <label
        htmlFor={checkboxId}
        className={cn(
          'flex items-start gap-2 text-sm',
          props.disabled && 'cursor-not-allowed opacity-50',
          !props.disabled && 'cursor-pointer',
          className,
        )}
      >
        <input
          type="checkbox"
          id={checkboxId}
          ref={ref}
          className="mt-0.5 h-4 w-4 shrink-0 rounded border-border bg-background accent-primary"
          {...props}
        />
        {label && <span>{label}</span>}
      </label>
    );
  },
);
Checkbox.displayName = 'Checkbox';

export { Checkbox };