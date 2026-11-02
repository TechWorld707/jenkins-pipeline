FROM nginxinc/nginx-unprivileged:alpine
USER root
# Apply available Alpine security fixes to all inherited packages, including curl.
RUN apk upgrade --no-cache
COPY index.html /usr/share/nginx/html/index.html
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY observability.conf.template /etc/nginx/templates/00-observability.conf.template
ENV OBSERVABILITY_ENABLED=false RELEASE_SHA=unknown NGINX_ERROR_LOG_LEVEL=error
USER nginx
EXPOSE 8080
