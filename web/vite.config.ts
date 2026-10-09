import { defineConfig, type ProxyOptions } from "vite";
import react from "@vitejs/plugin-react";

const proxy: Record<string, ProxyOptions> = {
  "/api": {
    target: "http://localhost:8000",
    changeOrigin: true,
    configure: (proxyServer) => {
      proxyServer.on("proxyReq", (proxyReq, request) => {
        // The loopback-only backend compares Origin to its own base URL.
        // Accept browser requests from this exact local UI; preserve other origins
        // so the backend can reject them. This proxy is not a deployment auth layer.
        const origin = request.headers.origin;
        if (
          origin === "http://127.0.0.1:5174" ||
          origin === "http://localhost:5174"
        )
          proxyReq.setHeader("origin", "http://localhost:8000");
      });
    },
  },
  "/health": { target: "http://localhost:8000", changeOrigin: true },
  "/openapi.json": { target: "http://localhost:8000", changeOrigin: true },
};
export default defineConfig({
  plugins: [react()],
  server: { host: "127.0.0.1", port: 5174, strictPort: true, proxy },
  preview: { host: "127.0.0.1", port: 5174, strictPort: true, proxy },
});
