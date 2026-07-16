/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eef5fa",
          100: "#d6e6f1",
          200: "#adcce2",
          300: "#84b2d3",
          400: "#5b98c4",
          500: "#2B6D9A",
          600: "#22577b",
          700: "#19415c",
          800: "#102c3e",
          900: "#08161f",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
