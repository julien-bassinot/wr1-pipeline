import os
import argparse
from typing import List
import logging


def ndpi(src: List[str], dst: str) -> None:
    """
    :param src: list of source file paths
    :param dst: destination file path
    :return: None

    This method performs NDPI calculation on a set of input images and saves the result to the destination directory.

    Example usage:
        src = ['/tmp/input/SENTINEL2A_20210115-105852-555_L2A_T31TCJ_C_V2-2_FRE_B3.tif',
               '/tmp/input/SENTINEL2A_20210115-105852-555_L2A_T31TCJ_C_V2-2_FRE_B11.tif']
        dst = "/home/NDPI_20210115_T31TCJ.tif"
        waterSurf_Mask(src_directory, dst_directory)
    """
    expr = "\"(abs(im2b1+im1b1)<0.000001?0:(im2b1-im1b1)/(im2b1+im1b1))\""
    cmd_feature = "otbcli_BandMath -il " + ' '.join(src) + " -out " + dst + " -exp " + expr
    os.system(cmd_feature)
    return
    

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--src', nargs='+', help='Source paths B3 and B11.')
    parser.add_argument('--dst', default='./home/', help='Destination path.')

    logging.basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        level=logging.INFO,
        datefmt='%Y-%m-%d %H:%M:%S')

    logging.info('sub-process started.')
    args = parser.parse_args()
    ndpi(args.src, args.dst)
