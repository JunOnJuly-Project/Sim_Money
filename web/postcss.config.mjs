/** @type {import('postcss-load-config').Config} */
const config = {
  plugins: {
    // Tailwind CSS 4.x 는 PostCSS 플러그인으로 동작한다.
    "@tailwindcss/postcss": {},
  },
};

export default config;
