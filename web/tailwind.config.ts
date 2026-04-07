import type { Config } from "tailwindcss";

const config: Config = {
  // app/ 디렉터리의 모든 TSX/TS 파일에서 클래스 이름을 스캔한다.
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
};

export default config;
