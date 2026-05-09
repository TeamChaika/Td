/**
 * Unit/component тесты EventCard.
 *
 * Ожидает реализацию coder-frontend (3c):
 * - components/EventCard или features/events/EventCard
 *
 * Все тесты помечены skip до готовности 3c.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { within } from '@testing-library/react';

// ---------------------------------------------------------------------------
// Заглушка компонента — будет заменена на реальный импорт из 3c
// ---------------------------------------------------------------------------

// import { EventCard } from '@/features/events/event-card';

// Временная заглушка для компиляции
const EventCard = (_props: Record<string, unknown>) => null;

// ---------------------------------------------------------------------------
// Тесты
// ---------------------------------------------------------------------------

describe.skip('EventCard', () => {
  const defaultProps = {
    id: 'event-1',
    slug: 'new-year-2026',
    title: 'Новый год 2026',
    schedule: {
      type: 'single' as const,
      starts_at: '2026-12-31T20:00:00+03:00',
      ends_at: '2027-01-01T03:00:00+03:00',
    },
    location_name: 'Ресторан Чайка',
    image_card_url: 'https://s3.example.com/card.jpg',
    price_from_kopecks: 200000,
    is_sold_out: false,
    brand_color: '#FF5500',
  };

  it('renders event title', () => {
    // render(<EventCard {...defaultProps} />);
    // expect(screen.getByText('Новый год 2026')).toBeInTheDocument();
    expect(true).toBe(true);
  });

  it('renders formatted date', () => {
    // render(<EventCard {...defaultProps} />);
    // expect(screen.getByText(/31 декабря/)).toBeInTheDocument();
    expect(true).toBe(true);
  });

  it('renders formatted price', () => {
    // render(<EventCard {...defaultProps} />);
    // expect(screen.getByText(/2 000/)).toBeInTheDocument();
    expect(true).toBe(true);
  });

  it('applies brand color via CSS variable', () => {
    // const { container } = render(<EventCard {...defaultProps} />);
    // const card = container.firstElementChild;
    // expect(card).toHaveStyle({ '--primary': '#FF5500' });
    expect(true).toBe(true);
  });

  it('renders lazy-loaded image with alt text', () => {
    // render(<EventCard {...defaultProps} />);
    // const img = screen.getByRole('img');
    // expect(img).toHaveAttribute('loading', 'lazy');
    // expect(img).toHaveAttribute('alt', 'Новый год 2026');
    expect(true).toBe(true);
  });

  it('has aria-label on link', () => {
    // render(<EventCard {...defaultProps} />);
    // const link = screen.getByRole('link');
    // expect(link).toHaveAttribute('aria-label');
    expect(true).toBe(true);
  });

  it('shows sold out badge when is_sold_out is true', () => {
    // render(<EventCard {...defaultProps} is_sold_out={true} />);
    // expect(screen.getByText(/продано/i)).toBeInTheDocument();
    expect(true).toBe(true);
  });

  it('does not show sold out badge when is_sold_out is false', () => {
    // render(<EventCard {...defaultProps} is_sold_out={false} />);
    // expect(screen.queryByText(/продано/i)).not.toBeInTheDocument();
    expect(true).toBe(true);
  });

  it('renders location name', () => {
    // render(<EventCard {...defaultProps} />);
    // expect(screen.getByText('Ресторан Чайка')).toBeInTheDocument();
    expect(true).toBe(true);
  });

  it('links to event detail page', () => {
    // render(<EventCard {...defaultProps} />);
    // const link = screen.getByRole('link');
    // expect(link).toHaveAttribute('href', '/events/new-year-2026');
    expect(true).toBe(true);
  });
});