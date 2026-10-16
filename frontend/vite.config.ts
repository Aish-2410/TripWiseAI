import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// The dev server proxies /api to the FastAPI backend so no CORS or secrets are needed in the browser.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173, proxy: { "/api": { target: process.env.VITE_API_TARGET || "http://127.0.0.1:8000", changeOrigin: true } } },
  build: { chunkSizeWarningLimit: 900 },
});
