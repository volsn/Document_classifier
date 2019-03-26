import cv2
import numpy as np
import os
import zipfile
import PyPDF2
import io

try:
    from PIL import Image
except ImportError:
    import Image
import pytesseract


class Scanner:

    def __init__(self, path, file_name):

        if file_name.endswith('.zip') or file_name.endswith('.rar'):
            self.unzip(path, file_name)
            file_name = [f for f in listdir(path) if f.split('.')[0] == file_name.split('.')[0] and \
                            f.split('.')[-1] != file_name.split('.')[-1]]

        
        if file_name.endswith('.pdf'):
        	self.convert_to_image(path, file_name)


    def unzip(self, path, file_name):
        with zipfile.ZipFile(os.path.join(path, file_name), 'r') as zip_ref:
            zip_ref.extractall(path)

    def convert_to_image(self, path, file_name):

        reader = PyPDF2.PdfFileReader(open(os.path.join(path, file_name), "rb"))
 
        for page_num in range(reader.getNumPages()):
            page = reader.getPage(page_num)
            media = page.mediaBox
            size = (media[2], media[3])

            dst_pdf = PyPDF2.PdfFileWriter()
            dst_pdf.addPage(page)

            pdf_bytes = io.BytesIO()
            dst_pdf.write(pdf_bytes)
            pdf_bytes.seek(0)

            mode = 'RGB'
            print(pdf_bytes)
            img = Image.open(pdf_bytes)
            img.save('test.png')

    def extract_text(self, path, file_name):
        pass

        
if __name__ == '__main__':
	path = r'C:\Users\Kolia\source\repos\DocsParser\DocsParser'
	file_name = 'balance.pdf'
	
	Scanner = Scanner(path, file_name)
