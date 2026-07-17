/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        dark: {
          950: "#050508",
          900: "#0a0a0f",
          800: "#12121a",
          700: "#1c1c28",
          600: "#28283a"
        },
        cyber: {
          cyan: "#00f0ff",
          magenta: "#ff007f",
          yellow: "#ffea00",
          purple: "#9d4edd",
          green: "#39ff14"
        }
      },
      boxShadow: {
        glow: "0 0 15px rgba(0, 240, 255, 0.35)",
        "glow-magenta": "0 0 15px rgba(255, 0, 127, 0.35)",
        "glow-green": "0 0 15px rgba(57, 255, 20, 0.35)",
        "glow-purple": "0 0 15px rgba(157, 78, 221, 0.35)"
      }
    },
  },
  plugins: [],
}
