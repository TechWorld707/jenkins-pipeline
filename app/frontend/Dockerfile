FROM nginxinc/nginx-unprivileged:alpine
USER root
# Refresh the inherited Brotli package to include available security fixes.
RUN apk upgrade --no-cache brotli-libs
COPY index.html /usr/share/nginx/html/index.html
COPY nginx.conf /etc/nginx/conf.d/default.conf
USER nginx
EXPOSE 8080
