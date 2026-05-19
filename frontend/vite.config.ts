import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    // 5173 avoids clashing with Docker frontend (published on host :3000).
    port: 5173,
    strictPort: true,
    proxy: {
      "/health": "http://localhost:8000",
      "/query": "http://localhost:8000",
      "/inject": "http://localhost:8000",
      "/remember": "http://localhost:8000",
      "/decisions": "http://localhost:8000",
      "/contradictions": "http://localhost:8000",
    },
  },
});
