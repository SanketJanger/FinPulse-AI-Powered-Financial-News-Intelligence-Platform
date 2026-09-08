import type { Config } from "tailwindcss";

const withAlpha = (v: string) => `rgb(var(${v}) / <alpha-value>)`;

const config: Config = {
  darkMode: "class",
  content: [
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
    "./hooks/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: withAlpha("--background"),
        surface: withAlpha("--surface"),
        border: withAlpha("--border"),
        foreground: withAlpha("--foreground"),
        muted: withAlpha("--muted"),
        accent: withAlpha("--accent"),
        // Sentiment — CVD-checked; always shown next to a text label / legend.
        bullish: withAlpha("--bullish"),
        bearish: withAlpha("--bearish"),
        neutral: withAlpha("--neutral"),
      },
    },
  },
  plugins: [],
};
export default config;
