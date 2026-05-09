'use client';

/**
 * Страница настроек организации.
 */
import { useSession } from '@/lib/auth/use-session';
import { SettingsForm } from '@/features/organization/settings-form';
import { Spinner } from '@/components/ui/spinner';

export default function AdminSettingsPage() {
  const { organization, isAuthenticated } = useSession();

  if (!isAuthenticated || !organization) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner size="lg" />
      </div>
    );
  }

  return <SettingsForm organization={organization} />;
}