FROM python:3.11

RUN apt-get update && apt-get install ffmpeg libsm6 libxext6  -y

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY visu.py /app/visu.py

ENTRYPOINT [ "/bin/bash" ]