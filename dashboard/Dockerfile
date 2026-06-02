# Stage 1: Build Vue frontend
FROM node:22-alpine AS frontend-build
WORKDIR /build
COPY dashboard/frontend/package.json dashboard/frontend/package-lock.json ./
RUN npm ci
COPY dashboard/frontend/ ./
RUN npm run build

# Stage 2: Python app with built frontend
FROM ansible-agent-base:latest

COPY dashboard/ ./dashboard/
COPY orchestrator/ ./orchestrator/

# Copy built frontend into the dashboard
COPY --from=frontend-build /build/dist ./dashboard/frontend/dist/

EXPOSE 8080
CMD ["python", "-m", "dashboard.app"]
