/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // 소복소복 브랜드 팔레트
        brand: {
          DEFAULT: '#8B5E1C', // 로고/기본 브라운
          dark: '#6F4A12', // 버튼 진한 브라운
          light: '#B5915A',
        },
        accent: {
          DEFAULT: '#F5A623', // 오렌지 (FAB, 전송, 활성 탭)
          soft: '#FCE9CC', // 연한 오렌지 배경
        },
        cream: '#FBF7F1', // 앱 배경
        status: {
          red: '#E5484D', // 마감
          green: '#2FA36B', // 접수/성장
          blue: '#4C7DF0', // 안내/공고
        },
      },
      boxShadow: {
        card: '0 2px 12px rgba(80, 60, 30, 0.06)',
      },
      fontFamily: {
        sans: ['Pretendard', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
