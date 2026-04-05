import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["favicon.svg", "logo-white.svg", "logo-color.svg"],
      manifest: {
        name: "Howl Vision — One Health AI",
        short_name: "Howl Vision",
        description: "Veterinary AI copilot for accessible diagnosis",
        theme_color: "#009DB0",
        background_color: "#0a1628",
        display: "standalone",
        start_url: "/capture",
        icons: [
          { src: "/favicon.svg", sizes: "any", type: "image/svg+xml" },
          { src: "/logo-color.svg", sizes: "192x192", type: "image/svg+xml" },
        ],
      },
      workbox: {
        // Only cache static build artifacts — API responses must never be cached
        globPatterns: ["**/*.{js,css,html,svg,woff2,json}"],
      },
    }),
  ],
  server: {
    port: 20000,
    proxy: {
      "/api": {
        target: "http://localhost:20001",
        changeOrigin: true,
      },
    },
  },
});
