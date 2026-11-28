/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eef2f6",
          100: "#d7e0ea",
          200: "#b0c2d6",
          300: "#88a3c1",
          400: "#5f85ad",
          500: "#3a6690",
          600: "#1a3a5c",
          700: "#142d48",
          800: "#0f2033",
          900: "#08131f",
        },
        gold: "#E8B84B",
      },
      // Triam 28-11-2026: text a little larger across the screens (12 -> 13 px, 14 -> 14.5 px).
      fontSize: {
        xs: ["0.8125rem", { lineHeight: "1.15rem" }],
        sm: ["0.90625rem", { lineHeight: "1.35rem" }],
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
