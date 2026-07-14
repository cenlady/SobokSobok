/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // 따뜻하지만 업무 도구답게 채도를 낮춘 소복소복 팔레트
        brand: {
          DEFAULT: '#765337',
          dark: '#302922',
          light: '#BDA58F',
        },
        accent: {
          DEFAULT: '#C76C32',
          soft: '#F3E6DA',
        },
        cream: '#F6F2EB',
        surface: '#FFFDF9',
        line: '#E3DBD1',
        muted: '#746C63',
        status: {
          red: '#C54F49',
          green: '#4E7F62',
          blue: '#55748F',
        },
      },
      boxShadow: {
        card: '0 1px 2px rgba(48, 41, 34, 0.05)',
      },
      fontFamily: {
        sans: ['Pretendard', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
