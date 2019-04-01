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
import json


class Page:
    def __init__(self, **kwargs):

        self.image = None
        self.filename = None
        self.text = None
        self.type = None
        self.end_file = None
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

    FILE_END = [
        "Подпись",
    ]

    STATUTE = {
        'rights': ['общество вправе осуществлять', "общество обладает"],
        'authority': ['органами общества', "органами управления общества", "органом общества" \
            "органом управления общества"],
        'term': ['директор общества принимается', "срок полномочий", "директор назначается", "срок полномочий"],
        "powers": ['директор [а-я ]{0,20} осуществляет [а-я ]{0,20} полномочия:', 'директор общества:'],
        "limits": ['директор [а-я ]{0,20} не вправе'],
    }

    RENT = {
        'adress': ['по адресу:'],
        'time': ['срок аренды помещения:'],
        'landlord': ['\"арендодатель\"'],
    }

    MATCHES = {
    "balance": 
        ["бухгалтерский", "бухгалтерская", "бухгалтерское", "внеоборотные активы", "оборотные активы", \
        "капитал и резервы", "краткосрочные обязательства", "движение капитала", \
        "прибыль (убыток) до налогообложения", "чиcтая прибыль (убыток)"],
    "rent": ["договор аренды", "предмет договора", "использование помщения", \
        "срок аренды", "обязанности аредатора", "обязанности арендодателя", \
        "права арендатора", "права арендодателя", "порядок расчетов", \
        "арендная плата", "арендной платы", "ответственность сторон"],
    "statute": ["деятельности общества", "статус общества", \
        "капитал общества", "участника общества", "выход участника из общества", \
        "распределение прибыли", "фонды общества", "собрание участников"],
    "others": ["информационная картьта", "отчет", "заявление", "опись", "заключение", "лицензия", "свидетельство"],
    }    

    def __init__(self, path, file_name):

        self.files = []

        if file_name.endswith('.zip') or file_name.endswith('.rar'):
            self._unzip(path, file_name)
            file_name = [f for f in os.listdir(path) if f.split('.')[0] == file_name.split('.')[0] and \
                            f.split('.')[-1] != file_name.split('.')[-1]]
            file_name = file_name[0]

        if file_name.endswith('.pdf'):
            pages = self._convert_to_image(path, file_name, format='PDF')


        if file_name.endswith('.tif') or file_name.endswith('.tiff'):
            pages = self._convert_to_image(path, file_name, format='TIF')


        if not os.path.exists('tmp'):
            os.mkdir('tmp')
    
        name = 0
        for page in pages: 
            page.image.save(os.path.join('tmp', '{}.png'.format(name)))
            page.filename = '{}.png'.format(name)
            self.files.append(page)
            name += 1
        
        for file in self.files:
            file.get_text()
            file.type = self._define_type(file.text)

        for match in self.FILE_END:
            if re.search(match, page.text, flags=re.I):
                page.end_file = True

        self.documents = self._divide_into_documents()
        print(self.documents)

        answer = []

        for document in self.documents:
            doc = {}
            type_ = document[0].type 
            if type_ == 'statute':
                #return (rights, authority, term, powers, limits)
                context = {}
                data = self._analyze_statute(document)

                context['rights'] = data[0]
                context['authority'] = data[1]
                context['term'] = data[2]
                context['powers'] = data[3]
                context['limits'] = data[4]

                doc['type'] = 'statute'
                doc['context'] = context
            elif type_ == 'rent':
                context = {}
                data = self._analyze_rent(document)
                context['adress'] = data[0]
                context['time'] = data[1]
                context['landlord'] = data[2]
                
                doc['type'] = 'rent'
                doc['context'] = context
            elif type_ == 'balance':
                doc['type'] = 'balance'
            else:
                pass
                
            if doc != {}:
                answer.append(doc)

        print(answer)



    def _unzip(self, path, file_name):
        with zipfile.ZipFile(os.path.join(path, file_name), 'r') as zip_ref:
            zip_ref.extractall(path)

    def _convert_to_image(self, path, file_name, format=None):
        if format is None:
            return None
        
        elif format == 'PDF':
            pages = list()
            images = pdf2image.convert_from_path(file_name, dpi=200, fmt="png")
            for img in images:
                pages.append(Page(image=img))
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
                except Exception:
                    pass
            return pages

    def _define_type(self, text):

        for doc_type in self.MATCHES.keys():
            for match in self.MATCHES[doc_type]:
                if re.search(match, text, flags=re.I):
                    if doc_type == 'others':
                        return 'others/{}'.format(match)
                    return doc_type
    
    def _divide_into_documents(self):
        
        documents = []
        recent_document = []

        for page in self.files:
            recent_document.append(page)
            if page.end_file:
                documents.append(recent_document)
                recent_document = []
        if recent_document != []:
            documents.append(recent_document)

        return documents

    def _analyze_statute(self, document):
        
        text = ''

        for page in document:
            text += page.text

        rights = []
        for match in STATUTE['rights']:
            right = re.search(r'({} [а-я]*.)'.format(match), text, flags=re.I)
            if right:
                right.append(right)
        
        authority = []
        for match in STATUTE['authority']:
            authority_ = re.search(r'({} [а-я]*.)'.format(match), text, flags=re.I)
            if authority_:
                authority_.append(right)

        term = []
        for match in STATUTE['term']:
            term = re.search(r'({} [а-я]*.)'.format(match), text, flags=re.I)
            if term:
                term.append(right)

        powers = []
        for match in STATUTE['term']:
            term = re.search(r'({} [а-я]*.)'.format(match), text, flags=re.I)
            if term:
                term.append(right)

        limits = []
        for match in STATUTE['limits']:
            limits = re.search(r'({} [а-я]*.)'.format(match), text, flags=re.I)
            if limits:
                limits.append(right)

        return (rights, authority, term, powers, limits)


    def _analyze_rent(self, document):

        text = ''

        for page in document:
            text += page.text
        
        adress = ''
        for match in self.RENT['adress']:
            if re.search(r'{}  [а-я]*[^.(/\\]'.format(match), text, flags=re.I):
                adress = re.search(r'{}  ([а-я]*[^.(/\\])'.format(match), text, flags=re.I)
                break

        time = ''
        for match in self.RENT['time']:
            if re.search(r'{} [а-я 0-9]*[^.(/\\]'.format(match), text, flags=re.I):
                time = re.search(r'{} ([а-я 0-9]*[^.(/\\])'.format(match), text, flags=re.I)
                break

        landlord = []
        for match in self.RENT['landlord']:
            if re.search(r'{}'.format(match), text, flags=re.I):
                company = re.search(r'("[а-я]*")[()/\\,.а-я\s]*"арендодатель"', text, flags=re.I)
                name = re.search(r'([А-Я]{1}[а-я]*\s+){3}[()/\\,.а-я\s]*"арендодатель"', text)
                landlord.append(company)
                landlord.append(name)
                break 

        return (adress, time, landlord)


if __name__ == '__main__':
	
    scanner = Scanner(r'C:\Users\Kolia\Desktop\Classifier', sys.argv[1])
