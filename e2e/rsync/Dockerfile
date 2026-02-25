FROM alpine:3.19

RUN apk add --no-cache rsync

COPY rsyncd.conf /etc/rsyncd.conf
COPY rsyncd.secrets /etc/rsyncd.secrets
RUN chmod 600 /etc/rsyncd.secrets

RUN mkdir -p /data

EXPOSE 873

CMD ["rsync", "--daemon", "--no-detach", "--config=/etc/rsyncd.conf"]
