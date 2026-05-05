# Custom n8n image with the OnPrintShop community node baked in.
# Replaces the volume-mount install pattern so this image is portable
# (ECS, n8n.cloud Pro+, Render, Fly, self-hosted Docker).
#
# Build from repo root:
#   docker build -f n8n.Dockerfile -t api-hub-n8n:latest .
FROM node:20-alpine AS node-build
WORKDIR /build
COPY n8n-nodes-onprintshop/package.json n8n-nodes-onprintshop/package-lock.json ./
RUN npm ci
COPY n8n-nodes-onprintshop ./
RUN npm run build

FROM n8nio/n8n:latest
USER root
RUN mkdir -p /home/node/.n8n/custom \
 && chown -R node:node /home/node/.n8n/custom
COPY --from=node-build --chown=node:node /build/dist /home/node/.n8n/custom/n8n-nodes-onprintshop/dist
COPY --from=node-build --chown=node:node /build/package.json /home/node/.n8n/custom/n8n-nodes-onprintshop/package.json
USER node
ENV N8N_CUSTOM_EXTENSIONS=/home/node/.n8n/custom
