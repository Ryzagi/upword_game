# Frontend image — multi-stage: Node build → nginx static serve + reverse proxy.
# Built from repo root:
#   docker build -f frontend/Dockerfile -t word-describer-frontend .

# ---------- stage 1: build ----------
FROM node:20-alpine AS build

WORKDIR /src

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --no-audit --no-fund

COPY frontend/. ./
RUN npm run build

# ---------- stage 2: nginx ----------
FROM nginx:1.27-alpine AS runtime

# Drop the default site, install our reverse-proxy + SPA config.
RUN rm /etc/nginx/conf.d/default.conf
COPY frontend/nginx.docker.conf /etc/nginx/conf.d/word-describer.conf

# Static assets from the build stage.
COPY --from=build /src/dist /var/www/word-describer

# Note: we deliberately don't run `nginx -t` here. Our config references the
# `backend` service hostname, which only resolves once the compose network is
# up at runtime. nginx will validate (and fail fast) at container start.

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
