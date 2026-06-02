/** @type {import('workbox-build').GenerateSWConfig} */
module.exports = {
  swDest: "public/sw.js",
  globDirectory: ".next/static",
  globPatterns: ["**/*.{js,css,html,png,svg,ico,woff,woff2}"],
  // Precache offline-critical pages
  additionalManifestEntries: [
    { url: "/tasks", revision: null },
    { url: "/shopping", revision: null },
  ],
  runtimeCaching: [
    {
      // NetworkFirst for all API calls — fresh data when online, cached fallback offline
      urlPattern: /^https?:\/\/.*\/api\/v1\/.*/,
      handler: "NetworkFirst",
      options: {
        cacheName: "api-cache",
        networkTimeoutSeconds: 10,
        expiration: {
          maxEntries: 200,
          maxAgeSeconds: 24 * 60 * 60, // 1 day
        },
        cacheableResponse: {
          statuses: [0, 200],
        },
      },
    },
    {
      // CacheFirst for Next.js static assets
      urlPattern: /^\/_next\/static\/.*/,
      handler: "CacheFirst",
      options: {
        cacheName: "next-static",
        expiration: {
          maxEntries: 500,
          maxAgeSeconds: 30 * 24 * 60 * 60, // 30 days
        },
      },
    },
  ],
};
