# Stage 1: Build React SPA
FROM node:18-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json* ./

RUN npm install

COPY . .

RUN npm run build

# Stage 2: Serve built static files using Nginx
FROM nginx:alpine

# Copy custom Nginx configuration if needed, or default static location
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
