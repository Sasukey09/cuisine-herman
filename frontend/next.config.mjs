/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Produces a minimal self-contained server bundle for Docker deploys.
  output: "standalone",
  async headers() {
    // Defence-in-depth headers on every response. Deliberately NOT a full
    // content CSP (script-src/style-src): Next.js hydration relies on inline
    // scripts, so a strict policy would need per-request nonces and could break
    // rendering. `frame-ancestors 'none'` gives clickjacking protection without
    // changing how any page looks or behaves.
    const securityHeaders = [
      {
        key: "Strict-Transport-Security",
        value: "max-age=63072000; includeSubDomains",
      },
      { key: "X-Frame-Options", value: "DENY" },
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      { key: "Content-Security-Policy", value: "frame-ancestors 'none'" },
    ];
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
