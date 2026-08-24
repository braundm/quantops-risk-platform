FROM node:24.14.0-alpine AS builder

ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
RUN corepack enable && corepack prepare pnpm@11.15.0 --activate

WORKDIR /workspace
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY apps/web/package.json apps/web/package.json
RUN pnpm install --frozen-lockfile
COPY apps/web apps/web
RUN pnpm --filter @quantops/web build

FROM nginx:1.31.4-alpine AS runtime
COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /workspace/apps/web/dist /usr/share/nginx/html
RUN mkdir -p /var/cache/nginx \
    && touch /var/run/nginx.pid \
    && chown -R 101:101 /var/cache/nginx /var/run/nginx.pid
USER 101
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -q -O - http://127.0.0.1:8080/ >/dev/null || exit 1
