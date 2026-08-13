/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        brand: {
          dark: "#0F172A",     // Deep slate base
          card: "#1E293B",     // Secondary slate
          border: "#334155",   // Accent borders
          primary: "#6366F1",  // Electric Indigo
          secondary: "#06B6D4",// Cyber Cyan
          danger: "#EF4444",   // Coral Red
          warning: "#F59E0B",  // Neon Amber
          success: "#10B981"   // Emerald Green
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
