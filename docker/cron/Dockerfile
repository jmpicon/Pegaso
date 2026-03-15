FROM alpine:latest

# Install docker and bash for the backup script
RUN apk add --no-cache docker-cli bash curl postgresql-client

WORKDIR /app

# The crontab file will be mounted or copied
COPY config/crontab /etc/periodic/daily/pegaso-backup
RUN chmod +x /etc/periodic/daily/pegaso-backup

# Simple cron runner
CMD ["crond", "-f", "-l", "2"]
