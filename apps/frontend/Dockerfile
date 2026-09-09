# Stage 1: Build static assets
FROM node:22-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./

# NOTE: npm 10.9.8 (node:22-alpine's bundled version) hits a reproducible
# "Exit handler never called!" crash running `npm ci` against this lockfile.
# Upgrading npm first avoids it.
RUN npm install -g npm@11 && npm ci

COPY . .

ARG VITE_CORE_API_URL
ARG VITE_TRS_URL
ARG VITE_FIREBASE_API_KEY
ARG VITE_FIREBASE_AUTH_DOMAIN
ARG VITE_FIREBASE_PROJECT_ID
ARG VITE_FIREBASE_STORAGE_BUCKET
ARG VITE_FIREBASE_MESSAGING_SENDER_ID
ARG VITE_FIREBASE_APP_ID
ARG VITE_MEASUREMENT_ID
ENV VITE_CORE_API_URL=$VITE_CORE_API_URL \
    VITE_TRS_URL=$VITE_TRS_URL \
    VITE_FIREBASE_API_KEY=$VITE_FIREBASE_API_KEY \
    VITE_FIREBASE_AUTH_DOMAIN=$VITE_FIREBASE_AUTH_DOMAIN \
    VITE_FIREBASE_PROJECT_ID=$VITE_FIREBASE_PROJECT_ID \
    VITE_FIREBASE_STORAGE_BUCKET=$VITE_FIREBASE_STORAGE_BUCKET \
    VITE_FIREBASE_MESSAGING_SENDER_ID=$VITE_FIREBASE_MESSAGING_SENDER_ID \
    VITE_FIREBASE_APP_ID=$VITE_FIREBASE_APP_ID \
    VITE_MEASUREMENT_ID=$VITE_MEASUREMENT_ID

RUN npm run build

# Stage 2: Serve assets with Nginx (non-root)
FROM nginxinc/nginx-unprivileged:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
