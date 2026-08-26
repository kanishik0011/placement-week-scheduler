import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#111827",
        line: "#d7dee8",
        surface: "#f7f9fc",
        ok: "#0f766e",
        warn: "#b45309",
        danger: "#b91c1c"
      }
    }
  },
  plugins: []
};

export default config;

