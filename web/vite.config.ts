import path from "node:path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

// The built bundle is served by FastAPI from /srv/static, so it must be fully
// self-contained: every font, icon and script comes out of this build and
// nothing is fetched from a CDN at runtime (docs/DECISIONS.md D-13).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": path.resolve(import.meta.dirname, "./src") },
  },
  server: {
    port: 5173,
    // In development the API is the real stack. Streaming endpoints need the
    // proxy not to buffer, or the run trace arrives all at once at the end.
    proxy: {
      "/api": { target: "http://127.0.0.1:8117", changeOrigin: false },
    },
  },
  build: {
    // Built straight into the directory FastAPI serves. static/ is build
    // output now, never hand-written, and is gitignored.
    outDir: "../static",
    emptyOutDir: true,
    assetsInlineLimit: 0,
    sourcemap: false,
  },
})
