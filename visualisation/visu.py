import rioxarray as riox
from rasterio.enums import Resampling
import numpy as np
import cv2
from shapely import box, Polygon, MultiPolygon
from collections import defaultdict
import geopandas as gpd
from tqdm import tqdm
import xarray as xr
from affine import Affine
import argparse


def adjust_gamma(image, gamma=1.0):
    invGamma = 1.0 / gamma
    table = np.array([((i / 255.0) ** invGamma) * 255 for i in np.arange(0, 256)]).astype("uint8")
    return cv2.LUT(image, table)


def build_img(blue, green, red, date, tuile, save=False):
    img = np.zeros((blue.shape[0], blue.shape[1], 3), dtype=np.uint8)
    img[:,:,0] = np.clip(blue.values / np.percentile(blue.values.ravel(), 99.95) * 255, 0, 255).astype(np.uint8)
    img[:,:,0] = adjust_gamma(img[:,:,0], gamma=2)
    img[:,:,1] = np.clip(green.values / np.percentile(green.values.ravel(), 99.95) * 255, 0, 255).astype(np.uint8)
    img[:,:,1] = adjust_gamma(img[:,:,1], gamma=2)
    img[:,:,2] = np.clip(red.values / np.percentile(red.values.ravel(), 99.95) * 255, 0, 255).astype(np.uint8)
    img[:,:,2]  = adjust_gamma(img[:,:,2], gamma=2)
    if save:
        cv2.imwrite(f'./visualisation_{date}_{tuile}/RGB_{date}_{tuile}.png', img)
    return img


def array_to_raster(vignette_mask, frame, frame_img, raster):
    vignette_tiff = xr.DataArray(
        data=vignette_mask.astype(np.uint8) *255,
        coords={
            'x': raster.coords['x'][frame_img[0][0]: frame_img[1][0]].values,
            'y': raster.coords['y'][frame_img[0][1]: frame_img[1][1]].values,
            'band': 1,
            'spatial_ref': 0
        },
        dims=raster.dims,
        attrs=raster.attrs
    )
    vignette_tiff.rio.write_crs(
        raster.rio.crs,
        inplace=True,
    ).rio.set_spatial_dims(
        x_dim="x",
        y_dim="y",
        inplace=True,
    ).rio.write_coordinate_system(inplace=True)
    mat = raster.rio.transform()
    transform = Affine(mat[0], mat[1], frame[0][0], mat[3], mat[4], frame[0][1])
    vignette_tiff.rio.write_transform(transform, inplace=True)
    return vignette_tiff


# Construction du mask NDPI
def build_mask(green, swir, date, tuile, save=False):
    swir = swir.rio.reproject(
        swir.rio.crs,
        shape=(swir.rio.height * 2, swir.rio.width * 2),
        resampling=Resampling.bilinear,
    )
    a = (swir.values - green.values).astype(np.float32)
    b = (swir.values + green.values).astype(np.float32)
    ndpi = np.divide(a, b, out=np.zeros_like(a), where=b!=0)
    mask = ndpi < 0
    if save:
        cv2.imwrite(f'./visualisation_{date}_{tuile}/NDPI_{date}_{tuile}.png', ((ndpi + 1) * 127.5).astype(np.uint8))
        cv2.imwrite(f'./visualisation_{date}_{tuile}/MASK_{date}_{tuile}.png', mask.astype(np.uint8) * 255)
    return mask


# Chargement de la base inpe
def load_inpe(inpe_path, raster):
    data = gpd.read_file(inpe_path)
    # Conversion dans le crs de la tuile
    data.to_crs(raster.rio.crs, inplace=True)
    # Sélection des contours présents dans la tuile
    data = data[data.geometry.intersects(box(*raster.rio.bounds()))]
    data.reset_index(inplace=True)
    return data


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
    #all_polygons = MultiPolygon(all_polygons)
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


# tuile = 'T31TCJ'
# date = '20210415'
# "./SENTINEL2A_20210415-105852-555_L2A_T31TCJ_C_V2-2_FRE_B2.tif"
# "./SENTINEL2A_20210415-105852-555_L2A_T31TCJ_C_V2-2_FRE_B3.tif"
# "./SENTINEL2A_20210415-105852-555_L2A_T31TCJ_C_V2-2_FRE_B4.tif"
# "./SENTINEL2A_20210415-105852-555_L2A_T31TCJ_C_V2-2_FRE_B11.tif"
# "INPE_BDD_0-1ha_FrMetro.gpkg"
def main(workdir, tuile, date, B2, B3, B4, B11, inpe):
    ID = data.loc[i, 'id']
    blue = riox.open_rasterio(B2).squeeze()
    green = riox.open_rasterio(B3).squeeze()
    red = riox.open_rasterio(B4).squeeze()
    swir = riox.open_rasterio(B11).squeeze()
    img = build_img(blue, green, red, date, tuile, save=True)
    mask = build_mask(green, swir, date, tuile, save=True)
    data = load_inpe(inpe, green)
    data.to_file(f'{workdir}/visualisation_{date}_{tuile}/INPE_{tuile}.gpkg')
    for i in tqdm(data.index):
        # left, bottom, right, top
        frame = data.loc[i, 'geometry'].bounds
        buffer = np.max((50, 0.2 * np.sqrt(data.loc[i, 'geometry'].area)))
        # [[left, top], [right, bottom]]
        frame = [[frame[0] - buffer, frame[3] + buffer],
                 [frame[2] + buffer, frame[1] - buffer]]
        frame_img = [epsg_to_pixel(x, green) for x in frame]
        vignette_mask = mask[frame_img[0][1]: frame_img[1][1], frame_img[0][0]: frame_img[1][0]]
        vignette_tiff = array_to_raster(vignette_mask, frame, frame_img, green)
        vignette_tiff.rio.to_raster(f'{workdir}/visualisation_{date}_{tuile}/MASKS/{data.loc[i, 'id']}_{date}_{tuile}.tif')
        vignette_world = img[frame_img[0][1]: frame_img[1][1], frame_img[0][0]: frame_img[1][0]].copy()
        inpe_poly = []
        # convert inpe polygons in pixels and draw them on image
        for j in range(len(data.loc[i, 'geometry'].geoms)):
            coord = [[x, y] for x, y, z in data.loc[i, 'geometry'].geoms[j].exterior.coords]
            coord = [epsg_to_pixel(x, green) for x in coord]
            coord = [(x[0]-frame_img[0][0], x[1]-frame_img[0][1]) for x in coord]
            inpe_poly.append(Polygon(coord).buffer(0))
            cv2.drawContours(vignette_world, [np.array(coord, dtype=np.int32)], 0, (0, 0, 255), 1)
        contours = mask_to_polygons(vignette_mask.astype(np.uint8), 10)
        contours = resolve_geometries(contours, 10)
        inpe_poly = resolve_geometries(inpe_poly, 10)
        if len(contours) == 0:
            cv2.imwrite(f'{workdir}/visualisation_{date}_{tuile}/NOVECTOR/{ID}_{date}_{tuile}.png', vignette_world)
        is_contour = False
        for contour in contours:
            if np.any([contour.intersects(inpe_poly[j]) for j in range(len(inpe_poly))]):
                is_contour = True
                cv2.drawContours(vignette_world, [np.array(contour.exterior.coords, dtype=np.int32)], 0, (255, 0, 0), 1)
            cv2.imwrite(f'{workdir}/visualisation_{date}_{tuile}/VECTOR/{ID}_{date}_{tuile}.png', vignette_world)
        if not is_contour:
            for contour in contours:
                cv2.drawContours(vignette_world, [np.array(contour.exterior.coords, dtype=np.int32)], 0, (255, 0, 0), 1)
            cv2.imwrite(f'{workdir}/visualisation_{date}_{tuile}/NOVECTOR/{ID}_{date}_{tuile}.png', vignette_world)
    return


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--workdir', help='Destination directory')
    parser.add_argument('--tuile')
    parser.add_argument('--date')
    parser.add_argument('--B2')
    parser.add_argument('--B3')
    parser.add_argument('--B4')
    parser.add_argument('--B11')
    parser.add_argument('--inpe')

    args = parser.parse_args()
    main(args.workdir, args.tuile, args.date, args.B2, args.B3, args.B4, args.B11, args.inpe)