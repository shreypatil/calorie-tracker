import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    // The frontend always calls same-origin `/api`, so there is no CORS setup
    // in development and no API base URL baked into the bundle.
    proxy: {
      "/api": {
        target: process.env.VITE_API_TARGET ?? "http://localhost:8000",
        changeOrigin: true,
      },
      // The dev-only docs read the API's live OpenAPI spec, which FastAPI serves from the root
      // rather than under /api. Without this the Docs → API page hits the Vite server instead.
      "/openapi.json": {
        target: process.env.VITE_API_TARGET ?? "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
