# syntax=docker/dockerfile:1
# =============================================================================
# auto-monitor ws-gateway (Node 22 + TypeScript) - hardened multi-stage image
# =============================================================================
# ---------- stage 1: compile TypeScript ----------
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

# ---------- stage 2: runtime (production dependencies only) ----------
FROM node:22-alpine AS runtime
LABEL org.opencontainers.image.title="auto-monitor-ws-gateway" \
      org.opencontainers.image.description="WebSocket gateway of auto-monitor" \
      org.opencontainers.image.licenses="MIT"
ENV NODE_ENV=production
RUN apk upgrade --no-cache
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --no-audit --no-fund --ignore-scripts && npm cache clean --force
COPY --from=build /app/dist ./dist
USER node
EXPOSE 4000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD wget -qO- http://127.0.0.1:4000/healthz > /dev/null || exit 1
CMD ["node", "dist/server.js"]
