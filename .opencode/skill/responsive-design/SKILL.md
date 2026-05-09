---
name: responsive-design
description: Применяй при вёрстке UI, адаптивных лейаутов, работе с брейкпоинтами, мобильной версии, Tailwind-классами для разных размеров экрана. Mobile-first, container queries, fluid typography, touch targets.
---

# Responsive Design

## Принципы

1. **Mobile-first всегда.** Базовые стили без префикса — для мобильных. `sm:`, `md:`, `lg:`, `xl:` добавляют на больших экранах. Никогда не начинай с десктопа и не override вниз.
2. **Content > breakpoints.** Ломай лейаут там, где контент этого требует, а не по фиксированным устройствам. Используй min/max значения, которые выглядят хорошо.
3. **Container queries > viewport queries** для переиспользуемых компонентов. Компонент не должен зависеть от размера экрана — он зависит от своего контейнера.

## Tailwind breakpoints (дефолт)

```
sm  → 640px   (большой телефон, маленький планшет)
md  → 768px   (планшет)
lg  → 1024px  (маленький десктоп)
xl  → 1280px  (десктоп)
2xl → 1536px  (большой десктоп)
```

Не придумывай свои без необходимости. Если нужны — добавляй в `tailwind.config` с осмысленными именами (`tablet`, `desktop`), а не цифрами.

## Container Queries

Используй `@container` для компонентов, которые появляются в разных местах с разной шириной:

```tsx
<div className="@container">
  <div className="grid grid-cols-1 @md:grid-cols-2 @lg:grid-cols-3 gap-4">
    {/* карточки адаптируются к ширине родителя, а не viewport */}
  </div>
</div>
```

Требует `@tailwindcss/container-queries` плагин.

## Fluid Typography

Для заголовков и крупного текста — плавное масштабирование через `clamp()`:

```css
h1 { font-size: clamp(1.75rem, 1.25rem + 2.5vw, 3rem); }
```

Формула: `clamp(MIN, PREFERRED, MAX)`, где `PREFERRED = MIN + (MAX-MIN) * ((100vw - MIN_WIDTH) / (MAX_WIDTH - MIN_WIDTH))`.

Для Tailwind — через theme.extend.fontSize или utility-плагин.

## Touch Targets

- **Минимум 44×44px** для любого интерактивного элемента на мобильном (WCAG 2.5.5, Apple HIG).
- На Tailwind это `min-h-11 min-w-11` или `h-11` для кнопок.
- Между кликабельными элементами — gap не меньше 8px.

## Типовые паттерны

### Адаптивная сетка карточек
```tsx
<div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 md:gap-6">
```

### Навигация: бургер → горизонтальное меню
```tsx
<nav>
  <button className="md:hidden" aria-label="Open menu">☰</button>
  <ul className="hidden md:flex gap-6">...</ul>
</nav>
```

### Sticky sidebar + основной контент
```tsx
<div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-8">
  <aside className="lg:sticky lg:top-4 lg:h-[calc(100vh-2rem)] lg:overflow-y-auto">...</aside>
  <main>...</main>
</div>
```

### Формы: одна колонка на мобильном, две на широком
```tsx
<form className="grid grid-cols-1 md:grid-cols-2 gap-4">
  <Field className="md:col-span-2" /> {/* поле на всю ширину */}
  <Field />
  <Field />
</form>
```

## Изображения

- `next/image` с `sizes` по брейкпоинтам — обязательно. Без `sizes` браузер грузит максимально возможную версию.
- `srcset` для адаптивных PNG/JPG вне Next.
- `<picture>` с `<source media=...>` для art direction (разный кроп на мобиле/десктопе).

## Viewport meta

Всегда в `<head>`:
```html
<meta name="viewport" content="width=device-width, initial-scale=1" />
```
Не указывай `maximum-scale=1` или `user-scalable=no` — это ломает доступность.

## Тёмная тема

- Используй `dark:` варианты Tailwind, не отдельные темы через классы-обёртки.
- Цвета — через CSS-переменные или Tailwind theme tokens, а не хардкод.
- Учитывай `prefers-color-scheme`, но давай возможность переключить вручную.

## Тестирование

- DevTools Device Toolbar: минимум проверить iPhone SE (375px), iPhone 14 Pro (393px), iPad (768px), десктоп (1280px+).
- Реальные устройства отличаются: safe areas на iPhone, разные шрифты по умолчанию, софт-клавиатура съедает высоту.
- `100vh` на мобильных — проблема (адресная строка). Используй `100dvh` (dynamic viewport height).

## Антипаттерны

- ❌ `hidden xl:block` для контента, важного на мобильном (скрываешь = выбрасываешь)
- ❌ Фиксированные ширины в пикселях для лейаута
- ❌ `overflow: hidden` на `body` без необходимости (ломает iOS scroll)
- ❌ Отдельный мобильный сайт (`m.example.com`) вместо responsive
- ❌ `@media (max-width: ...)` как основа — это desktop-first, ломает принцип mobile-first
