FROM node:22-alpine

WORKDIR /app

COPY package.json ./
RUN npm install --omit=dev

COPY server.js ./

ENV CORTEX_API_URL=http://api:8000

# CORTEX_API_KEY is required whenever ENVIRONMENT=production. Without it, the
# MCP server refuses all tool calls instead of falling back to the legacy
# X-Cortex-Roles header (see mcp/server.js and .env.example).
ENV ENVIRONMENT=production
ENV CORTEX_API_KEY=

CMD ["npm", "start"]
