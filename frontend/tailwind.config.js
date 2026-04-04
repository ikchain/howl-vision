/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ocean: {
          deep: '#0a1628',
          surface: '#0d2137',
          elevated: '#112d3c',
          border: '#1a3a52',
          'border-hover': '#2a5570',
        },
        teal: {
          DEFAULT: '#009DB0',
          light: '#62C2DC',
          deep: '#006B80',
          text: '#4DBDD4',
          hover: '#00B3C8',
        },
        content: {
          primary: '#e0f2f7',
          secondary: '#8ba3b8',
          muted: '#6d8fa5',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
