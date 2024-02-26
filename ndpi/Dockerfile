FROM orfeotoolbox/otb:latest

COPY ndpi.py /usr/local/bin/ndpi.py
RUN chmod +x /usr/local/bin/ndpi.py

ENTRYPOINT [ "python3", "/usr/local/bin/ndpi.py" ]
