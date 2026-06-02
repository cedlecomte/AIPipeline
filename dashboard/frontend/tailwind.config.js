/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts}'],
  theme: {
    extend: {
      colors: {
        primary: { DEFAULT: '#667eea', dark: '#5a67d8' },
        surface: { DEFAULT: '#1e1e2e', light: '#2a2a3e', lighter: '#363650' },
        accent: '#764ba2',
      },
    },
  },
  plugins: [],
}
