FROM alpine:3.19

WORKDIR /app
COPY init_config.sh /usr/local/bin/init_config.sh
RUN chmod +x /usr/local/bin/init_config.sh

ENTRYPOINT ["/usr/local/bin/init_config.sh"]
