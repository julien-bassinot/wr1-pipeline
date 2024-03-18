import geopandas as gpd
import rioxarray as riox
from shapely.geometry import box, mapping, Polygon, MultiPolygon
import numpy as np
import cv2


# [longitude, latitude] -> [longitude, latitude]
def epsg_to_pixel(x, raster):
    mat = raster.rio.transform()
    u = np.clip(np.round((x[0] - mat[2]) / mat[0]), 0, raster.shape[1]).astype(int)
    v = np.clip(np.round((mat[5] - x[1]) / -mat[4]), 0, raster.shape[0]).astype(int)
    return [u, v]


def pixel_to_epsg(x, raster):
    mat = raster.rio.transform()
    return x * np.array([mat[0], mat[4]]) + np.array([mat[2], mat[5]])


def get_lake(geometry, idx, date, tuile, raster, whole_lake):
    # for each lake crop a ROI in raster
    frame = list(geometry.geoms)[0]
    # left, bottom, right, top
    frame = frame.bounds
    # [[left, top], [right, bottom]]
    frame = [[frame[0] - 50, frame[3] + 50],
             [frame[2] + 50, frame[1] - 50]]
    frame = [epsg_to_pixel(x, raster) for x in frame]
    # Check if there's a lake detected in raster
    if whole_lake[frame[0][1] + (frame[1][1] - frame[0][1]) // 2, frame[0][0] + (frame[1][0] - frame[0][0]) // 2] == 0:
        return
    lake = whole_lake[frame[0][1]: frame[1][1], frame[0][0]: frame[1][0]]

    # retrieve lake contour from binary raster
    contours, hierarchy = cv2.findContours(lake, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)  # cv2.CHAIN_APPROX_NONE

    # in case of several contours choose the one at the center
    dst = 999999
    contour = None
    for c in contours:
        M = cv2.moments(c)
        if M["m00"] == 0:
            continue
        cX = int(M["m10"] / M["m00"])
        cY = int(M["m01"] / M["m00"])
        dst_c = np.sqrt((cX - lake.shape[1] // 2) ** 2 + (cY - lake.shape[0] // 2) ** 2)
        if dst_c < dst:
            contour = c
            dst = dst_c
    if contour is None or dst > 5:
        return

    # convert contour into a polygon
    contour = contour.squeeze()
    contour = contour + np.array([frame[0][0], frame[0][1]])
    contour = pixel_to_epsg(contour, raster)
    contour = Polygon(contour)

    # add contour to result list
    return ({"id_inpe": idx,
             "date": date,
             "tuile": tuile,
             "geometry": contour
             })


def vectorize(inpe_path, raster_path, dst, date, tuile):
    data = gpd.read_file(inpe_path)
    img = riox.open_rasterio(raster_path).squeeze()

    # CRS Lambert 93
    img = img.rio.write_nodata(0, inplace=True)
    img = img.rio.reproject(data.crs, nodata=0)
    img = img.astype('bool')
    img = img.astype('uint8')

    # Select shapes inside raster
    data = data[data.geometry.intersects(box(*img.rio.bounds()))]

    # prepare a list for storing the results
    whole_lake = img.values

    result = data.apply(lambda row: get_lake(row.geometry, row.id, date, tuile, img, whole_lake), axis=1)
    result.dropna(inplace=True)
    result = gpd.GeoDataFrame(list(result.values), crs=data.crs)
    result.to_file(dst)

    return

