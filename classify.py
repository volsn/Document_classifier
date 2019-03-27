import json
import os
import shutil
import time

from PIL import Image
import pdf2image
from pytesseract import image_to_string
from docs_parser import *


def extract_pdf(filename):
    pages = list()
    images = pdf2image.convert_from_path(filename, dpi=200, fmt="png")
    for img in images:
        pages.append(Page(image=img))
    return pages


def detect():
    start = time.time()
    result = dict()
    if request.method == "POST" and "file0" in request.files:
        files = list()
        try:
            os.mkdir("tmp")
        except FileExistsError:
            pass
        n = 0
        file = None
        for i in range(0, 5):
            image = request.files.get("file%s" % i, None)
            if image:
                print(image.filename)
                filename = image.filename.lower()
                root, ext = os.path.splitext(filename)
                if ext.lower() == ".pdf":
                    saveto = "tmp/pdf-%s.pdf" % i
                    image.save(saveto)
                    pages = extract_pdf(saveto)
                    ext = ".png"
                    i = 0
                    for page in pages:
                        n += 1
                        saveto = "tmp/image-%s%s" % (n, ext)
                        page.image.save(saveto)
                        page.filename = saveto
                        files.append(page)
                else:
                    n += 1
                    saveto = "tmp/image-%s%s" % (n, ext)
                    image.save(saveto)
                    files.append(Page(image=saveto, filename=saveto))
        filetime = time.time()
        if files:
            if detect_passport(files):
                result["doctype"] = "passport"
            elif detect_lease_contract(files):
                result["doctype"] = "lease_contract"
            elif detect_balance(files):
                result["doctype"] = "balance"
            elif detect_chart(files):
                result["doctype"] = "chart"
            else:
                result["doctype"] = "unknown"
            shutil.rmtree("tmp")
        detecttime = time.time()
        result["filetime"] = filetime - start
        result["detecttime"] = detecttime - filetime
    else:
        print("Empty result")
    print(json.dumps(result, indent=4))
    return json.dumps(result, indent=4)


if __name__ == '__main__':
    pass
