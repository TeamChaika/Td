# Многостадийная сборка: dev и prod

# --- base: общие инструменты ---
FROM node:20-alpine AS base

WORKDIR /app

# pnpm через corepack (встроен в Node 20+)
RUN corepack enable && corepack prepare pnpm@9 --activate

# --- dev: для локальной разработки ---
FROM base AS dev

# Копируем только манифесты для кэша зависимостей
COPY package.json ./
# pnpm-lock.yaml появится после первого pnpm install локально
COPY pnpm-lock.yaml* ./

# В dev разрешаем отсутствие лока (первый запуск); в prod — строго frozen
RUN pnpm install

# Код монтируется volume'ом в docker-compose
EXPOSE 3000

CMD ["pnpm", "dev"]

# --- builder: сборка prod-бандла ---
FROM base AS builder

COPY package.json pnpm-lock.yaml* ./
RUN pnpm install --frozen-lockfile

COPY . .
RUN pnpm build

# --- prod: минимальный runtime ---
FROM node:20-alpine AS prod

WORKDIR /app

ENV NODE_ENV=production

# Копируем standalone-сборку Next.js
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

# Непривилегированный пользователь
RUN addgroup -g 1001 -S nodejs && adduser -S nextjs -u 1001 && chown -R nextjs:nodejs /app
USER nextjs

EXPOSE 3000

CMD ["node", "server.js"]
