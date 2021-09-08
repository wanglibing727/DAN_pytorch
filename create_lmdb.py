import os
import lmdb  # install lmdb by "pip install lmdb"
import cv2
import numpy as np
from tqdm import tqdm
import six
from PIL import Image
import scipy.io as sio
from tqdm import tqdm
import re


def check_image_is_valid(imageBin):
    if imageBin is None:
        return False
    imageBuf = np.fromstring(imageBin, dtype=np.uint8)
    img = cv2.imdecode(imageBuf, cv2.IMREAD_GRAYSCALE)
    imgH, imgW = img.shape[0], img.shape[1]
    if imgH * imgW == 0:
        return False
    return True


def write_cache(env, cache):
    with env.begin(write=True) as txn:
        for k, v in cache.items():
            txn.put(k.encode(), v)


def _is_difficult(word):
    assert isinstance(word, str)
    return not re.match('^[\w]+$', word)


def create_dataset(outputPath, imageList, lexiconList=None, checkValid=True):
    nSamples = len(imageList)
    env = lmdb.open(outputPath, map_size=1099511627)
    cache = {}
    cnt = 1
    imageList = list(map(lambda x: x.strip('\n'), imageList))
    for i in range(nSamples):
        imagePath = imageList[i]
        label = imagePath.split('.')[0].split('_')[2]
        print(label)
        imagePath = os.path.join(images_dir, imagePath)
        print(imagePath)
        if len(label) == 0:
            continue
        # if not os.path.exists(imagePath):
        #     print('%s does not exist' % imagePath)
        #     continue
        with open(imagePath, 'rb') as f:
            imageBin = f.read()
        if checkValid:
            if not check_image_is_valid(imageBin):
                print('%s is not a valid image' % imagePath)
                continue

        imageKey = 'image-%09d' % cnt
        labelKey = 'label-%09d' % cnt
        cache[imageKey] = imageBin
        cache[labelKey] = label.encode()
        if lexiconList:
            lexiconKey = 'lexicon-%09d' % cnt
            cache[lexiconKey] = ' '.join(lexiconList[i])
        if cnt % 1000 == 0:
            write_cache(env, cache)
            cache = {}
            print('Written %d / %d' % (cnt, nSamples))
        cnt += 1
    nSamples = cnt - 1
    cache['num-samples'] = str(nSamples).encode()
    write_cache(env, cache)
    print('Created dataset with %d samples' % nSamples)


if __name__ == "__main__":
    root = os.getcwd()
    data_dir = os.path.join(root, 'data', 'val.txt')
    images_dir = os.path.join(root, 'images')
    lmdb_output_path = os.path.join(root, 'lmdbdata', 'data', 'test')

    if not os.path.exists(lmdb_output_path):
        os.makedirs(lmdb_output_path)

    with open(data_dir, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    create_dataset(lmdb_output_path, lines)
