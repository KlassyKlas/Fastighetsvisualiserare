# Steg 1: bygg SPA:n. OBS: Vite läser VITE_*-variabler vid BYGGTID —
# Mapbox-token måste in som build-arg, inte som runtime-miljövariabel.
FROM node:24-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ARG VITE_MAPBOX_TOKEN
ENV VITE_MAPBOX_TOKEN=$VITE_MAPBOX_TOKEN

RUN npm run build

# Steg 2: servera statiskt med nginx (proxar /api till backend)
FROM nginx:1.30-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
