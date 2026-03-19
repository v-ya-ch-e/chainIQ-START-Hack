FROM node:22-alpine AS base
WORKDIR /app
ENV npm_config_fetch_retries=5 \
    npm_config_fetch_retry_factor=2 \
    npm_config_fetch_retry_mintimeout=20000 \
    npm_config_fetch_retry_maxtimeout=120000 \
    npm_config_fetch_timeout=300000

FROM base AS deps
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

FROM deps AS dev
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0", "--port", "3000"]

FROM deps AS builder
ARG BACKEND_INTERNAL_URL=http://organisational-layer:8000
ARG LOGICAL_BACKEND_INTERNAL_URL=http://logical-layer:8080
ENV BACKEND_INTERNAL_URL=${BACKEND_INTERNAL_URL}
ENV LOGICAL_BACKEND_INTERNAL_URL=${LOGICAL_BACKEND_INTERNAL_URL}
COPY . .
RUN npm run build

FROM base AS runner
ENV NODE_ENV=production

COPY package.json package-lock.json ./
RUN npm ci --omit=dev --no-audit --no-fund

COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/next.config.ts ./next.config.ts

EXPOSE 3000
CMD ["npm", "run", "start", "--", "--hostname", "0.0.0.0", "--port", "3000"]
