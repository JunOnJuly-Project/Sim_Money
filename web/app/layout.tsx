import type { Metadata } from "next";
import "./globals.css";
// WHY: KaTeX 수식 렌더를 위해 전역 CSS를 루트 레이아웃에서 한 번만 로드한다.
import "katex/dist/katex.min.css";

export const metadata: Metadata = {
  title: "Sim Money — 유사 종목 탐색기",
  description: "개인 전용 실험 도구: 유사도 기반 종목 탐색",
};

/**
 * 루트 레이아웃.
 * 모든 페이지에서 공유되는 HTML 셸과 전역 스타일을 제공한다.
 */
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
