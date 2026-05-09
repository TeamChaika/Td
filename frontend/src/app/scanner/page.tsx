import Link from 'next/link';

import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';

export default function ScannerPage() {
  return (
    <main className="flex min-h-screen items-center justify-center px-6">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>QR-сканер билетов</CardTitle>
          <CardDescription>
            PWA-приложение для контролёров на входе. Реализация — Phase 8.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button asChild variant="outline" className="w-full">
            <Link href="/">← На главную</Link>
          </Button>
        </CardContent>
      </Card>
    </main>
  );
}
