import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    // The backend's CORS allowlist only permits port 5173. strictPort makes Vite
    // fail loudly if 5173 is taken instead of silently falling back to another port
    // (which would break every API call with a CORS error). See README.
    port: 5173,
    strictPort: true,
  },
});
