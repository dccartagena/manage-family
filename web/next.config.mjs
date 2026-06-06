/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  webpack: (config) => {
    // Alias @undecaf/zbar-wasm to the self-contained inlined variant (WASM bundled
    // as base64 — no separate .wasm file needed at runtime). Using an alias rather
    // than conditionNames avoids overwriting webpack's built-in browser/module/import
    // conditions which other packages (e.g. Supabase) depend on.
    config.resolve.alias = {
      ...config.resolve.alias,
      "@undecaf/zbar-wasm": new URL(
        "./node_modules/@undecaf/zbar-wasm/dist/inlined/index.mjs",
        import.meta.url
      ).pathname,
    };
    return config;
  },
  async headers() {
    return [
      {
        source: "/sw.js",
        headers: [
          {
            key: "Service-Worker-Allowed",
            value: "/",
          },
          {
            key: "Cache-Control",
            value: "no-cache",
          },
        ],
      },
    ];
  },
};

export default nextConfig;
