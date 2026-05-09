/**
 * Dashboard админки — заглушка «Будет здесь».
 */
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';

export default function AdminDashboardPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Dashboard</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Обзор продаж и показателей вашей организации.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { title: 'Выручка за неделю', value: '—' },
          { title: 'Продано билетов', value: '—' },
          { title: 'Активных событий', value: '—' },
          { title: 'Баланс кошелька', value: '—' },
        ].map((m) => (
          <Card key={m.title}>
            <CardHeader className="pb-2">
              <CardDescription>{m.title}</CardDescription>
              <CardTitle className="text-2xl">{m.value}</CardTitle>
            </CardHeader>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Dashboard будет здесь</CardTitle>
        </CardHeader>
        <CardContent>
          <CardDescription>
            Полный dashboard с графиками продаж и таблицами появится в следующих
            фазах разработки. Сейчас доступны базовые настройки организации.
          </CardDescription>
        </CardContent>
      </Card>
    </div>
  );
}