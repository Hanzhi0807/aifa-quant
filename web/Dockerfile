# Build stage
FROM node:20-alpine AS builder
WORKDIR /app

COPY web/package.json web/package-lock.json ./
RUN npm ci

COPY web/ ./
RUN npm run build

# Production stage
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/package.json ./

RUN adduser -D appuser
USER appuser

EXPOSE 3000
CMD ["node", "dist/boot.js"]
