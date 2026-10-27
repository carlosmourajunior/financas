# Estágio base: dependências instaladas uma vez
FROM node:22-alpine AS base
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .

# Desenvolvimento: servidor do Vite com recarga automática
FROM base AS dev
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# Build de produção
FROM base AS build
RUN npm run build

# Produção: arquivos estáticos servidos pelo nginx
FROM nginx:1.27-alpine AS prod
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
