import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const backend = "http://127.0.0.1:8000";
const apiPaths = [
  "/auth",
  "/catalog",
  "/events",
  "/me",
  "/leaderboard",
  "/sse",
  "/admin",
  "/health",
  "/explain",
];

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: Object.fromEntries(
      apiPaths.map((path) => [path, { target: backend, changeOrigin: true }]),
    ),
  },
});
