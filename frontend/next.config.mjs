/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  reactStrictMode: true,
  eslint: {
    dirs: ['src'],
  },
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'}/api/:path*`,
      },
    ];
  },
  images: {
    remotePatterns: [
      // Моки (будут удалены после перехода на S3)
      { protocol: 'https', hostname: 'images.unsplash.com' },
      // Dev MinIO / local S3
      { protocol: 'http', hostname: 'localhost', port: '9000' },
      { protocol: 'http', hostname: 'localhost', port: '9001' },
      { protocol: 'http', hostname: '127.0.0.1', port: '9000' },
      { protocol: 'http', hostname: '127.0.0.1', port: '9001' },
      // Production S3 (через переменную окружения)
      ...(process.env.NEXT_PUBLIC_S3_HOST
        ? [{ protocol: 'https', hostname: process.env.NEXT_PUBLIC_S3_HOST }]
        : []),
    ],
  },
  // typedRoutes включим в Phase 2, когда будут реальные страницы.
  // Пока многие ссылки ведут на будущие роуты — TS падает на литералах.
};

export default nextConfig;