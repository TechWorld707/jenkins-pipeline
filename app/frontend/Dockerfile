FROM nginxinc/nginx-unprivileged:alpine
USER root
# Apply available Alpine security fixes to all inherited packages, including curl.
RUN apk upgrade --no-cache
COPY index.html /usr/share/nginx/html/index.html
COPY nginx.conf /etc/nginx/conf.d/default.conf
USER nginx
EXPOSE 8080
