import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    // 백엔드 FastAPI 서버로 API 요청을 프록시한다.
    // 프론트엔드에서 CORS 없이 /api/:path* 로 호출하면 백엔드로 투명하게 전달된다.
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:8000/:path*",
      },
    ];
  },
};

export default nextConfig;
