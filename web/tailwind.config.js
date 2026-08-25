/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "var(--color-canvas)",
        surface: "var(--color-surface)",
        ink: "var(--color-ink)",
        muted: "var(--color-muted)",
        line: "var(--color-line)",
        coral: {
          50: "var(--color-coral-50)",
          100: "var(--color-coral-100)",
          200: "var(--color-coral-200)",
          300: "var(--color-coral-300)",
          400: "var(--color-coral-400)",
          500: "var(--color-coral-500)",
          600: "var(--color-coral-600)",
          700: "var(--color-coral-700)",
        },
        lavender: {
          50: "var(--color-lavender-50)",
          100: "var(--color-lavender-100)",
          200: "var(--color-lavender-200)",
        },
      },
      borderRadius: {
        DEFAULT: "var(--radius-sm)",
        sm: "var(--radius-sm)",
        md: "var(--radius-md)",
        lg: "var(--radius-lg)",
        xl: "var(--radius-xl)",
      },
      boxShadow: {
        soft: "var(--shadow-soft)",
        card: "var(--shadow-card)",
      },
      spacing: {
        "page-x": "var(--space-page-x)",
        "page-y": "var(--space-page-y)",
      },
      fontFamily: {
        sans: ["var(--font-sans)"],
      },
    },
  },
  plugins: [],
};
