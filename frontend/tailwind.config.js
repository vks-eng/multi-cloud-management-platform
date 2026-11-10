/** @type {import('tailwindcss').Config} */
// CloudOrbit design tokens: a dark-first palette with an "orbit" cyan/violet accent.
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        canvas: '#0a0f1e',
        surface: '#10172b',
        elevated: '#172036',
        line: '#243050',
        ink: '#e7ebf6',
        muted: '#9aa6c4',
        faint: '#6b7799',
        orbit: {
          50: '#ecfeff',
          200: '#a5f3fc',
          300: '#67e8f9',
          400: '#22d3ee',
          500: '#06b6d4',
          600: '#0891b2',
          700: '#0e7490',
        },
        nebula: { 300: '#c4b5fd', 400: '#a78bfa', 500: '#8b5cf6', 600: '#7c3aed' },
        aws: '#f59e0b',
        azure: '#38bdf8',
        gcp: '#34d399',
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'Segoe UI', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'Consolas', 'monospace'],
      },
      boxShadow: { glow: '0 0 0 1px rgba(34,211,238,0.25), 0 8px 30px -12px rgba(34,211,238,0.35)' },
    },
  },
  plugins: [],
};
