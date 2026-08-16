FROM node:22-slim AS build

WORKDIR /app

# Dependencies install from the lockfile alone, so editing source does not
# invalidate this layer.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Build-time, not runtime: Vite substitutes this into the bundle during compilation, so setting it
# in the running container would do nothing. Off by default — the docs ship only when asked for.
ARG VITE_SHOW_DOCS=false
ENV VITE_SHOW_DOCS=$VITE_SHOW_DOCS
RUN npm run build


FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
