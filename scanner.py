import cv2
import numpy as np
import os
import zipfile
import PyPDF2
import io
import pdf2image
from PIL import Image
from pytesseract import image_to_string
import sys
import re


class Page:
    def __init__(self, **kwargs):

        self.image = None
        self.filename = None
        self.text = None
        self.type = None
        if kwargs:
            self.__dict__.update(kwargs)

    def get_text(self):

        self.text = image_to_string(self.image, lang="rus")

    def _prepare_for_reading(self):

        img = cv2.imread(self.filename)
        im_gray = cv2.imread(self.filename, cv2.IMREAD_GRAYSCALE)

        (thresh, im_bw) = cv2.threshold(im_gray, 128, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)

        thresh = 127
        im_bw = cv2.threshold(im_gray, thresh, 255, cv2.THRESH_BINARY)[1]
        edges = cv2.Canny(im_bw, 50, 150, apertureSize = 3)
        cv2.imwrite('edges.png', edges)

        cv2.imwrite('bw_image.png', im_bw)


class Scanner:

    MATCHES = {
    "balance": 
        ["бухгалтерский", "внеоборотные активы", "оборотные активы", \
        "капитал и резервы", "краткосрочные обязательства", "движение капитала", \
        "прибыль (убыток) до налогообложения", "чиcтая прибыль (убыток)"],
    "others": ["Отчет", "Заявка"],
    }

    def __init__(self, path, file_name):

        self.files = []

        if file_name.endswith('.zip') or file_name.endswith('.rar'):
            self._unzip(path, file_name)
            file_name = [f for f in listdir(path) if f.split('.')[0] == file_name.split('.')[0] and \
                            f.split('.')[-1] != file_name.split('.')[-1]]


        if file_name.endswith('.pdf'):
            pages = self._convert_to_image(path, file_name, format='PDF')


        if file_name.endswith('.tif') or file_name.endswith('.tiff'):
            pages = self._convert_to_image(path, file_name, format='TIF')


        if not os.path.exists('tmp'):
            os.mkdir('tmp')

        name = 0
        for page in pages: 
            #page.image.save(os.path.join('tmp', '{}.png'.format(name)))
            page.filename = '{}.png'.format(name)
            self.files.append(page)
            name += 1


        for file in self.files:
            file.get_text()


        for file in self.files:
            file.type = self._define_type(file.text)
            print(file.type)
        


    def _unzip(self, path, file_name):
        with zipfile.ZipFile(os.path.join(path, file_name), 'r') as zip_ref:
            zip_ref.extractall(path)

    def _convert_to_image(self, path, file_name, format=None):
        if format is None:
            return None
        
        elif format == 'PDF':
            pages = list()
            print('foo')
            images = pdf2image.convert_from_path(file_name, dpi=200, fmt="png")
            print('bar')
            name = 0
            for img in images:
                pages.append(Page(image=img))
                img.save(os.path.join('tmp', '{}.png'.format(name)))
                name += 1
            return pages

        elif format == 'TIF':
            pages = list()
            img = Image.open(file_name)

            for i in range(10):
                try:
                    img.seek(i)
                except EOFError:
                    break
                
                try:
                    pages.append(Page(image=img))
                except Error:
                    pass
            return pages

    def _define_type(self, text):

        for doc_type in self.MATCHES.keys():
            for match in self.MATCHES[doc_type]:
                if re.search(match, text, flags=re.I):
                    return doc_type




if __name__ == '__main__':
	
    scanner = Scanner(r'C:\Users\Kolia\Desktop\Classifier', sys.argv[1])
