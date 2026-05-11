FROM node:22-alpine

WORKDIR /app

COPY package.json ./
RUN npm install --omit=dev

COPY server.js ./

ENV CORTEX_API_URL=http://api:8000

CMD ["npm", "start"]
