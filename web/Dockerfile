# 이미지명을 docker.io/library/... 로 못박는다: OpenShift 빌드(buildah)는 레지스트리가 여러 개라
# `nginx:alpine` 처럼 짧은 이름이 모호하면 "short-name resolution enforced but cannot prompt
# without a TTY" 로 빌드가 죽는다. docker/compose 에서는 동작이 같다.
FROM docker.io/library/node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM docker.io/library/nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
