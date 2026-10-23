"""Make a 2 MB JPEG with no EXIF or location data, for load_test.js -e PHOTO=.

    python tests/load/make_test_photo.py test-photo-2mb.jpg
"""
import sys

import numpy as np
from PIL import Image

# Random pixels barely compress, so the file stays near 2 MB.
pixels = (np.random.default_rng(20261023).random((1500, 1900, 3)) * 255).astype("uint8")
Image.fromarray(pixels).save(sys.argv[1], quality=80)
print(sys.argv[1])
