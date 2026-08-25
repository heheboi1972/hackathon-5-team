# 이미지명을 docker.io/library/... 로 못박는다: OpenShift 빌드(buildah)는 레지스트리가 여러 개라
# `nginx:alpine` 처럼 짧은 이름이 모호하면 "short-name resolution enforced but cannot prompt
# without a TTY" 로 빌드가 죽는다. docker/compose 에서는 동작이 같다.
FROM docker.io/library/node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# nginx-unprivileged: OpenShift 는 컨테이너를 임의의 non-root UID 로 돌린다.
# 기본 nginx 이미지는 /var/cache/nginx 에 못 쓰고(Permission denied) 80 포트도 못 연다(<1024).
# 이 이미지는 8080 을 쓰고 필요한 디렉터리 권한이 gid 0 에 열려 있어 그대로 뜬다.
FROM docker.io/nginxinc/nginx-unprivileged:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 8080
