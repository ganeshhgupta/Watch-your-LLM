/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#0f0f0f',
        card: '#1a1a1a',
        border: '#2a2a2a',
        accent: '#3b82f6',
        'accent-hover': '#2563eb',
        muted: '#6b7280',
        success: '#22c55e',
        danger: '#ef4444',
        warning: '#f59e0b',
      },
    },
  },
  plugins: [],
}
