# Build stage
FROM node:20-alpine AS build

WORKDIR /app

# 패키지 매니저 파일 복사 및 의존성 설치
COPY package.json package-lock.json ./
RUN npm ci

# 소스 코드 및 설정 파일 복사
COPY . .

# 빌드 타임 환경변수 (API 접속 URL 등)
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

# TypeScript 타입 체크 및 Vite 빌드 실행
RUN npm run build

# Runtime stage
FROM nginx:1.27-alpine

# Nginx 커스텀 설정 적용
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 빌드 결과물 복사
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 5173

CMD ["nginx", "-g", "daemon off;"]
