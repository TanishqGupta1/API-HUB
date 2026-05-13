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
# Use /opt/custom-nodes so the node survives the n8n_data volume mount at /home/node/.n8n
RUN mkdir -p /opt/custom-nodes/n8n-nodes-onprintshop \
 && chown -R node:node /opt/custom-nodes
COPY --from=node-build --chown=node:node /build/dist /opt/custom-nodes/n8n-nodes-onprintshop/dist
COPY --from=node-build --chown=node:node /build/package.json /opt/custom-nodes/n8n-nodes-onprintshop/package.json
# node_modules is required so peer dependencies (n8n-workflow, etc.) resolve
# at runtime — without it n8n fails to load the node and silently reports
# "Unrecognized node type".
COPY --from=node-build --chown=node:node /build/node_modules /opt/custom-nodes/n8n-nodes-onprintshop/node_modules
USER node
ENV N8N_CUSTOM_EXTENSIONS=/opt/custom-nodes
