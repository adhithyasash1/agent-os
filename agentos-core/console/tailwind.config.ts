import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}"
  ],
  theme: {
    extend: {
      colors: {
        ink: "var(--ink)",
        muted: "var(--muted)",
        shell: "var(--shell)",
        panel: "var(--panel)",
        line: "var(--line)",
        accent: "var(--accent)",
        gold: "var(--gold)",
        success: "var(--success)",
        danger: "var(--danger)"
      },
      boxShadow: {
        panel: "0 24px 90px rgba(2, 6, 23, 0.25)"
      },
      fontFamily: {
        sans: ["var(--font-sans)", "sans-serif"],
        serif: ["var(--font-serif)", "serif"]
      },
      backgroundImage: {
        "shell-glow":
          "radial-gradient(circle at top left, rgba(56, 189, 248, 0.18), transparent 30%), radial-gradient(circle at top right, rgba(245, 158, 11, 0.14), transparent 28%), linear-gradient(180deg, #06101b 0%, #0a1628 55%, #050d18 100%)"
      }
    }
  },
  plugins: []
};

export default config;
