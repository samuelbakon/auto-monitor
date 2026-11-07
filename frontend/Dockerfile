# syntax=docker/dockerfile:1
# =============================================================================
# auto-monitor frontend (Nuxt 3) - hardened multi-stage image
#  - pinned base image (pin the digest too: see docs/04-container-security.md)
#  - build tools stay in the build stage, only .output ships to production
#  - OS packages patched, runs as non-root, code owned by root (read-only for app)
# =============================================================================
# ---------- stage 1: build ----------
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

# ---------- stage 2: runtime ----------
FROM node:22-alpine AS runtime
LABEL org.opencontainers.image.title="auto-monitor-frontend" \
      org.opencontainers.image.description="Nuxt chat UI of auto-monitor" \
      org.opencontainers.image.licenses="MIT"
ENV NODE_ENV=production NITRO_HOST=0.0.0.0 NITRO_PORT=3000
RUN apk upgrade --no-cache
WORKDIR /app
COPY --from=build /app/.output ./.output
USER node
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD wget -qO- http://127.0.0.1:3000/api/_health > /dev/null || exit 1
CMD ["node", ".output/server/index.mjs"]
