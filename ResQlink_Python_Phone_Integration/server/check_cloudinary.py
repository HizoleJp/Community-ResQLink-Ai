import os, socket
from pathlib import Path
from dotenv import load_dotenv

socket.setdefaulttimeout(15)
load_dotenv(Path(__file__).with_name(".env"), override=True)

import cloudinary
import cloudinary.api

cloudinary.config(secure=True)
print("cloud name:", cloudinary.config().cloud_name)
try:
    print("ping:", cloudinary.api.ping())
except Exception as e:
    print("ping FAILED:", type(e).__name__, str(e)[:150])