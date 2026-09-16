FROM node:20-slim AS builder
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

# Desenvolvimento (hot reload)
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
