FROM ghcr.io/osgeo/gdal:ubuntu-full-latest

COPY waterSurf_Mask.py /app/waterSurf_Mask.py
RUN chmod a+x /app/waterSurf_Mask.py

ENTRYPOINT [ "python3", "/app/waterSurf_Mask.py" ]
