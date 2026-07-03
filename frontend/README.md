# 🎨 soboksobok Frontend

React, TypeScript, Vite, Tailwind CSS 기반의 **soboksobok** 프론트엔드 서비스입니다.  
프로젝트 클론 후 로컬 개발 환경을 설정하고 실행하는 방법은 아래 가이드를 참고하세요.

---

## 🛠️ 개발 환경 요구사항
* **Node.js** (버전 18 이상 권장, LTS 버전 권장)
* **npm** (Node Package Manager)

---

## 🚀 빠른 시작 가이드 (Quick Start)

### 1. 패키지 설치
프론트엔드 디렉토리(`frontend/`)로 이동한 후, 필요한 패키지 의존성을 설치합니다.

```bash
# 프론트엔드 디렉토리로 이동
cd frontend

# 의존성 패키지 설치
npm install
```

---

### 2. 개발 서버 실행
설치가 완료되면 Vite 개발 서버를 구동합니다.

```bash
# 로컬 개발 서버 실행
npm run dev
```

서버가 구동되면 브라우저를 열고 다음 URL로 접속하세요.
* **로컬 접속 주소:** [http://localhost:5173](http://localhost:5173)

---

### 3. 프로젝트 빌드 및 검사
배포용 번들을 빌드하거나 코드의 품질 및 문법을 검사하기 위해 아래 스크립트를 사용할 수 있습니다.

* **TypeScript 타입 체크 및 Vite 프로덕션 빌드:**
  ```bash
  npm run build
  ```
* **Oxlint를 사용한 빠른 린트 검사:**
  ```bash
  npm run lint
  ```

---

## 📂 디렉토리 구조 설명
```text
frontend/
├── dist/              # 빌드 완료 시 생성되는 배포 번들 폴더
├── public/            # 정적 파일 (파비콘, 이미지 등) 폴더
├── src/
│   ├── assets/        # 이미지, 폰트 등 정적 에셋 폴더
│   ├── components/    # 재사용 가능한 UI 컴포넌트 폴더
│   ├── data/          # Mock 데이터 또는 정적 데이터 관리 폴더
│   ├── lib/           # 스토리지(LocalStorage) 등 유틸리티 함수 폴더
│   ├── screens/       # 페이지 단위 컴포넌트 폴더
│   ├── App.tsx        # 메인 라우터 및 레이아웃 설정
│   ├── main.tsx       # React 앱 진입점
│   ├── index.css      # Tailwind CSS 진입점 및 전역 CSS 설정
│   └── types.ts       # 공통 TypeScript 타입 선언 파일
├── index.html         # HTML 진입점 파일
├── package.json       # 프로젝트 패키지 설정 및 스크립트 파일
└── tsconfig.json      # TypeScript 컴파일러 설정
```
