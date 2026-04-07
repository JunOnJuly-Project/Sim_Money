FROM node:20-alpine

WORKDIR /app

# WHY: package.json 만 먼저 복사해 node_modules 레이어를 캐시한다.
#      소스 변경 시 npm install 을 재실행하지 않아 빌드 속도가 향상된다.
COPY package.json ./

RUN npm install

COPY . .

ENV NEXT_TELEMETRY_DISABLED=1

EXPOSE 3000

# WHY: M1 단계에서는 dev 모드로 실행해 HMR 을 활성화한다.
#      프로덕션 빌드는 Stage 2 이후 prod 이미지로 분리한다.
CMD ["npm", "run", "dev"]
