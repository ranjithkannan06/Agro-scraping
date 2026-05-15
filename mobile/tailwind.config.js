/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./App.{js,jsx,ts,tsx}", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: "#16a34a", // Green theme for agriculture
        dark: "#1f2937",
        light: "#f3f4f6"
      }
    },
  },
  plugins: [],
}
