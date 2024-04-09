import geopandas as gpd
import rioxarray as riox
from shapely.geometry import box, mapping, Polygon, MultiPolygon
from collections import defaultdict
import numpy as np
import cv2
import argparse
import logging


def epsg_to_pixel(x, raster):
    mat = raster.rio.transform()
    u = np.clip(np.round((x[0] - mat[2]) / mat[0]), 0, raster.shape[1]).astype(int)
    v = np.clip(np.round((mat[5] - x[1]) / -mat[4]), 0, raster.shape[0]).astype(int)
    return [u, v]


def mask_to_polygons(mask, min_area=10.):
    """Convert a mask ndarray (binarized image) to Multipolygons"""
    # first, find contours with cv2: it's much faster than shapely
    contours, hierarchy = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    if not contours:
        return []
    cnt_children = defaultdict(list)
    child_contours = set()
    assert hierarchy.shape[0] == 1
    for idx, (_, _, _, parent_idx) in enumerate(hierarchy[0]):
        if parent_idx != -1:
            child_contours.add(idx)
            cnt_children[parent_idx].append(contours[idx])
    # create actual polygons filtering by area (removes artifacts)
    all_polygons = []
    for idx, cnt in enumerate(contours):
        if idx not in child_contours and cv2.contourArea(cnt) >= min_area:
            assert cnt.shape[1] == 1
            poly = Polygon(
                shell=cnt[:, 0, :],
                holes=[c[:, 0, :] for c in cnt_children.get(idx, [])
                       if cv2.contourArea(c) >= min_area])
            all_polygons.append(poly)
    return all_polygons


def resolve_geometries(contours, min_area):
    new_contours = []
    for cnt in contours:
        if cnt.is_valid:
            new_contours.append(cnt)
        else:
            cnt = cnt.buffer(0)
            if cnt.geom_type == 'Polygon':
                new_contours.append(cnt)
            else:
                for c in cnt.geoms:
                    if c.area > min_area:
                        new_contours.append(c)
    return new_contours


def get_lake(geometry, idx, date, tuile, raster):
    frame = geometry.bounds
    buffer = np.max((50, 0.2 * np.sqrt(geometry.area)))
    frame = [[frame[0] - buffer, frame[3] + buffer],
             [frame[2] + buffer, frame[1] - buffer]]
    frame_img = [epsg_to_pixel(x, raster) for x in frame]
    vignette_mask = raster[frame_img[0][1]: frame_img[1][1], frame_img[0][0]: frame_img[1][0]]
    inpe_poly = []
    for j in range(len(geometry.geoms)):
        coord = [[x, y] for x, y, z in geometry.geoms[j].exterior.coords]
        coord = [epsg_to_pixel(x, raster) for x in coord]
        coord = [(x[0]-frame_img[0][0], x[1]-frame_img[0][1]) for x in coord]
        inpe_poly.append(Polygon(coord).buffer(0))
    contours = mask_to_polygons(vignette_mask.values.astype(np.uint8), 10)
    contours = resolve_geometries(contours, 10)
    inpe_poly = resolve_geometries(inpe_poly, 10)
    if len(contours) == 0:
        return
    list_polygon = []
    for contour in contours:
        if np.any([contour.intersects(inpe_poly[j]) for j in range(len(inpe_poly))]):
            list_polygon.append(contour)
    if len(list_polygon) != 0:
        return ({"id_inpe": idx,
                 "date": date,
                 "tuile": tuile,
                 "geometry": MultiPolygon(list_polygon)
                 })
    else:
        return


def vectorize(inpe, src, dst, date, tuile):
    data = gpd.read_file(inpe)
    img = riox.open_rasterio(src).squeeze().rio.write_nodata(0, inplace=True)

    # convert inpe to tile crs
    lambert_93_crs = data.crs
    data.to_crs(img.rio.crs, inplace=True)

    result = data.apply(lambda row: get_lake(row.geometry, row.id, date, tuile, img), axis=1)
    result.dropna(inplace=True)
    result = gpd.GeoDataFrame(list(result.values), crs=data.crs)
    result.to_crs(lambert_93_crs, inplace=True)
    result.to_file(dst)

    return


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--inpe', help='INPE geopackage lake database for the dedicated raster.')
    parser.add_argument('--src', help='WaterSurf_mask raster.')
    parser.add_argument('--dst', help='Destination of result geopackage')
    parser.add_argument('--date', help='Raster date')
    parser.add_argument('--tile', help='Raster tile')

    logging.basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        level=logging.INFO,
        datefmt='%Y-%m-%d %H:%M:%S')

    logging.info('sub-process started.')
    args = parser.parse_args()
    vectorize(args.inpe, args.src, args.dst, args.date, args.tile)
