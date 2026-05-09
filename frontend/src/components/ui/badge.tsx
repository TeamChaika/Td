import { cn } from '@/lib/utils/cn';

interface BadgeProps {
  variant?: 'default' | 'success' | 'warning' | 'destructive';
  children: React.ReactNode;
  className?: string;
}

const variantStyles: Record<NonNullable<BadgeProps['variant']>, string> = {
  default: 'bg-secondary text-secondary-foreground',
  success: 'bg-emerald-600/20 text-emerald-400',
  warning: 'bg-amber-600/20 text-amber-400',
  destructive: 'bg-red-600/20 text-red-400',
};

export function Badge({ variant = 'default', children, className }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium',
        variantStyles[variant],
        className,
      )}
    >
      {children}
    </span>
  );
}