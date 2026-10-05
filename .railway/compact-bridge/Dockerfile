FROM postgres:18
COPY continue_restore.sh /app/continue_restore.sh
RUN chmod 700 /app/continue_restore.sh
CMD ["bash", "/app/continue_restore.sh"]
