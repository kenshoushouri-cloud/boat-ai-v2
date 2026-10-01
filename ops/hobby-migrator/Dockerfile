FROM postgres:18
ENTRYPOINT []
COPY run.sh /usr/local/bin/hobby-migration-worker
RUN chmod 0755 /usr/local/bin/hobby-migration-worker
CMD ["/usr/local/bin/hobby-migration-worker"]
