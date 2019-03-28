FROM node:alpine

RUN apk add yarn

COPY . .

RUN yarn install
RUN yarn add -D serve
RUN yarn run build

EXPOSE 8080

CMD yarn run serve -s -l 8080 build/