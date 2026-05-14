import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      "/health": "http://localhost:8000",
      "/query": "http://localhost:8000",
      "/inject": "http://localhost:8000",
      "/contradictions": "http://localhost:8000",
    },
  },
});
