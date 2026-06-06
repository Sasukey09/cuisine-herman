/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Produces a minimal self-contained server bundle for Docker deploys.
  output: "standalone",
};

export default nextConfig;
