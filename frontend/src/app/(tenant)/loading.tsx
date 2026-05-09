/**
 * Loading state для страниц внутри (tenant) группы.
 */
import { Skeleton } from '@/components/ui/skeleton';

export default function TenantLoading() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6 sm:py-16">
      <Skeleton className="h-10 w-64 mb-8" />
      <div className="space-y-4">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-5/6" />
        <Skeleton className="h-4 w-4/6" />
      </div>
    </div>
  );
}