/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        infrastructure: {
          planerad: '#f59e0b',
          pågående: '#3b82f6',
          avslutad: '#22c55e',
        },
        property: {
          bostad: '#14b8a6',
          kontor: '#a855f7',
          handel: '#f97316',
          industri: '#ef4444',
          utbildning: '#06b6d4',
          villa: '#84cc16',
        },
      },
    },
  },
  plugins: [],
};
