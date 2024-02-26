import os
import argparse
from typing import List, Tuple


def ndpi(src: List[str], dst: str, date: str, tile: str) -> Tuple[str, str]:
    """
    :param src: list of source file paths
    :param dst: destination directory path
    :param date: date of the NDPI
    :param tile: tile number of the NDPI
    :return: a tuple containing the date and tile number of the NDPI

    This method performs NDPI calculation on a set of input images and saves the result to the destination directory.

    Example usage:
        src = ['/tmp/input/SENTINEL2A_20210115-105852-555_L2A_T31TCJ_C_V2-2_FRE_B4.tif',
               '/tmp/input/SENTINEL2A_20210115-105852-555_L2A_T31TCJ_C_V2-2_FRE_B8.tif']
        dst = "/home/"
        date = "20210115"
        tile = "T31TCJ"
        waterSurf_Mask(src_directory, dst_directory, image_date, image_tile)
    """
    expr = "\"(abs(im2b1+im1b1)<0.000001?0:(im2b1-im1b1)/(im2b1+im1b1))\""
    feature_out = dst + "NDPI" + '_' + date + '_' + tile + '.tif'
    cmd_feature = "otbcli_BandMath -il " + ' '.join(src) + " -out " + feature_out + " -exp " + expr
    os.system(cmd_feature)
    return date, tile
    

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--src', nargs='+', help='Source directories.')
    parser.add_argument('--dst', default='./home/', help='Destination directory.')
    parser.add_argument('--date', help='Specific date, format: YYYYMMDD')
    parser.add_argument('--tile', type=str, default='T31TCJ', help='Tile identifier.')
    
    args = parser.parse_args()
    ndpi(args.src, args.dst, args.date, args.tile)
