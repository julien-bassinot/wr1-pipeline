FROM orfeotoolbox/otb:latest

COPY ndpi.py /app/ndpi.py
RUN chmod a+x /app/ndpi.py

ENTRYPOINT [ "python3", "/app/ndpi.py" ]
