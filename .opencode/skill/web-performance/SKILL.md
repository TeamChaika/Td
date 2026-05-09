---
name: web-performance
description: Применяй при оптимизации производительности фронтенда, работе с Core Web Vitals (LCP, INP, CLS), bundle size, изображениями, шрифтами, кешированием, ленивой загрузкой, RSC/SSR/ISR.
---

# Web Performance

## Core Web Vitals — целевые значения

| Метрика | Хорошо | Плохо |
|---|---|---|
| **LCP** (Largest Contentful Paint) | ≤ 2.5s | > 4.0s |
| **INP** (Interaction to Next Paint) | ≤ 200ms | > 500ms |
| **CLS** (Cumulative Layout Shift) | ≤ 0.1 | > 0.25 |
| **FCP** (First Contentful Paint) | ≤ 1.8s | > 3.0s |
| **TTFB** (Time to First Byte) | ≤ 0.8s | > 1.8s |

Замер: Lighthouse, WebPageTest, PageSpeed Insights, `web-vitals` npm-пакет в рантайме.

## LCP — ускорение главного контента

1. **Preload LCP-элемента.** Обычно hero-изображение или заголовок.
   ```html
   <link rel="preload" as="image" href="/hero.webp" fetchpriority="high" />
   ```
2. **Priority Hints.** `<img fetchpriority="high">` на LCP, `loading="lazy"` на всех остальных below-the-fold.
3. **В Next.js:** `<Image priority />` на LCP-картинку, остальные без `priority`.
4. **Серверный рендеринг** для критичного контента. SPA с пустым HTML → долгий LCP.
5. **CDN** для статики, edge-кеширование HTML через ISR/SSG где возможно.

## INP — отзывчивость

1. **Разбивай длинные задачи.** Никаких синхронных циклов > 50ms. Используй `scheduler.yield()` или `setTimeout(0)` для разбивки.
2. **Debounce / throttle** для событий onInput, onScroll, onResize. 150–300ms debounce для поиска.
3. **Виртуализация длинных списков.** `react-virtuoso`, `@tanstack/react-virtual` при > 100 элементов.
4. **Web Workers** для тяжёлых вычислений (парсинг, криптография, обработка больших JSON).
5. **Избегай лишних ре-рендеров.** `React.memo`, `useMemo`, `useCallback` — только там, где реально помогает (измерь Profiler'ом).

## CLS — стабильность лейаута

1. **Размеры изображений всегда.** `<img width="800" height="600">` или `aspect-ratio` в CSS. Без этого браузер не знает место.
2. **Шрифты:** `font-display: swap` + `size-adjust` для fallback-шрифта, чтобы метрики совпадали. Next.js `next/font` делает это автоматически.
3. **Резервируй место для динамического контента.** Скелетоны одинаковой высоты с финальным контентом. Не показывай «пусто» → «всё», только «скелетон» → «всё».
4. **Не вставляй контент выше viewport.** Рекламу, баннеры, cookie-попапы — либо фиксированной высоты заранее, либо не в потоке.

## Bundle Size

1. **Анализируй регулярно.** `next build` показывает размер страниц. `@next/bundle-analyzer`, `vite-bundle-visualizer`, `source-map-explorer`.
2. **Code splitting.** Динамические импорты для тяжёлых компонентов (модалки, редакторы, графики):
   ```tsx
   const Chart = dynamic(() => import('./Chart'), { ssr: false });
   ```
3. **Tree-shaking.** Импортируй named, не default из больших библиотек:
   ```ts
   import { format } from 'date-fns';        // ✅ tree-shakes
   import * as dateFns from 'date-fns';      // ❌ тянет всё
   ```
4. **Замена тяжёлых зависимостей:**
   - `moment` (290kb) → `date-fns` (tree-shakeable) или `dayjs` (2kb)
   - `lodash` → `lodash-es` (tree-shakeable) или нативные методы
   - `axios` → нативный `fetch` + лёгкая обёртка
5. **Target current browsers.** Не транспилируй ES2020 в ES5 без нужды — лишние полифиллы.

## Изображения

1. **Форматы:** AVIF > WebP > JPEG. Fallback через `<picture>` или next/image (делает сам).
2. **Размеры:** атрибут `sizes` обязателен для responsive изображений. Без него грузится максимум.
   ```tsx
   <Image
     src="/card.jpg"
     width={1200}
     height={800}
     sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
     alt="..."
   />
   ```
3. **Lazy loading:** `loading="lazy"` на всё, что ниже viewport. На LCP — `eager` / `priority`.
4. **Сжатие:** quality 75–85 для фото, 90+ для иллюстраций с текстом.

## Шрифты

1. **Self-host через `next/font`** (или `@fontsource`). Google Fonts CDN = +2 DNS запроса + иногда лаг.
2. **Только нужные начертания.** 3–4 weight максимум. Каждый дополнительный = лишние KB.
3. **Subsetting:** только нужные наборы символов (latin, cyrillic). Не грузи CJK если не используешь.
4. **`font-display: swap`** — текст виден сразу fallback-шрифтом, потом плавно меняется. Но осторожно с CLS (см. выше).
5. **Variable fonts** часто выгоднее нескольких статических.

## Кеширование

1. **HTTP headers:**
   - Статика с хешем в имени → `Cache-Control: public, max-age=31536000, immutable`
   - HTML → `Cache-Control: no-cache` (или короткий max-age с revalidate)
2. **CDN** для статики обязателен. Vercel/Cloudflare/CloudFront.
3. **Service Worker** только если нужен offline. Иначе добавляет сложность без выигрыша.
4. **React Query / SWR** — `staleTime`, `cacheTime`. Данные, которые редко меняются (конфиги, справочники) — `staleTime: Infinity`.

## Next.js App Router — специфика

1. **RSC по умолчанию.** `"use client"` только там, где нужна интерактивность. Всё остальное — серверные компоненты (ноль JS в бандле).
2. **Streaming:** `loading.tsx` и `<Suspense>` для поэтапной отдачи. Медленные части не блокируют быстрые.
3. **`revalidate`** — ISR для данных, которые обновляются редко. `revalidate: 3600` = пересборка раз в час.
4. **`generateStaticParams`** для динамических роутов с известным набором.
5. **`fetch()` в серверных компонентах** автоматически кешируется. `fetch(url, { cache: 'no-store' })` для всегда свежих.

## Сеть

1. **HTTP/2 или HTTP/3.** Выключи раздельное доменное шардирование — оно мешает.
2. **Preconnect / dns-prefetch** для критичных третьих доменов (CDN, аналитика):
   ```html
   <link rel="preconnect" href="https://cdn.example.com" crossorigin />
   ```
3. **Compression:** Brotli предпочтительнее gzip. На Vercel/Cloudflare — по умолчанию.
4. **API ответы:** пагинация, поля по требованию (GraphQL / sparse fieldsets), не отдавай гигантские JSON «на всякий случай».

## JavaScript execution

1. **Defer/async для скриптов.** `<script async>` для аналитики, `defer` для всего остального. Никогда не блокирующий script в `<head>`.
2. **Third-party scripts** — главные убийцы производительности. Ревьюй каждый: нужен? можно загрузить позже? можно заменить серверным?
3. **Partytown** — вынос third-party scripts в Web Worker (Google Analytics, GTM, hotjar).
4. **`requestIdleCallback`** для некритичных задач (префетч, аналитика событий).

## Чеклист перед деплоем

- [ ] Lighthouse mobile ≥ 90 по Performance
- [ ] LCP < 2.5s на 4G
- [ ] Нет CLS от шрифтов и изображений
- [ ] Bundle первого роута < 200kb gzipped
- [ ] Изображения: AVIF/WebP, sizes заданы, lazy ниже viewport
- [ ] Шрифты: self-hosted, swap, subset
- [ ] Third-party scripts: async/defer, минимум
- [ ] Кеш-заголовки на статику и API

## Антипаттерны

- ❌ Одна огромная `_app.tsx` с десятками провайдеров — всё попадает в каждый бандл
- ❌ `import * as Icons from '@heroicons/react'` — тянет все иконки
- ❌ `useEffect(() => fetch(...), [])` в RSC-совместимом коде — теряешь серверный рендеринг
- ❌ Изображения в формате PNG для фото
- ❌ Подключение Google Fonts через `<link>` вместо next/font
- ❌ Синхронный analytics.js в `<head>`
