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
        // Static build artifacts only. API responses never cached.
        // ONNX models are runtime-cached below, NOT precached: workbox precache
        // is transactional — a single failed asset (e.g. the 20MB model on a
        // flaky mobile connection) silently breaks the whole install.
        globPatterns: ["**/*.{js,css,html,svg,woff2,json}"],
        runtimeCaching: [
          {
            // CacheFirst: once stored, served from disk without network.
            // Dedicated cache name survives cleanupOutdatedCaches across SW updates.
            urlPattern: ({ url }) => url.pathname === "/models/dermatology_int8.onnx",
            handler: "CacheFirst",
            options: {
              cacheName: "howl-vision-models-v1",
              expiration: {
                maxEntries: 1,
                maxAgeSeconds: 60 * 60 * 24 * 365,
              },
              cacheableResponse: {
                statuses: [0, 200],
              },
              rangeRequests: false,
            },
          },
          {
            // onnxruntime-web ships its WebAssembly runtime as a separate ~25MB
            // .wasm asset. Without caching it, offline inference fails before
            // ever reaching the model: ort.InferenceSession.create() fetches
            // the wasm first, hits NetworkError, and rejects.
            urlPattern: ({ url }) => url.pathname.endsWith(".wasm"),
            handler: "CacheFirst",
            options: {
              cacheName: "howl-vision-runtime-v1",
              expiration: {
                maxEntries: 5,
                maxAgeSeconds: 60 * 60 * 24 * 365,
              },
              cacheableResponse: {
                statuses: [0, 200],
              },
              rangeRequests: false,
            },
          },
        ],
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
