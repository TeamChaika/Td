/**
 * Platform dashboard — редиректит на /platform/organizations.
 */
import { redirect } from 'next/navigation';

export default function PlatformDashboardPage() {
  redirect('/platform/organizations');
}