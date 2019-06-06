#!/usr/bin/env python
import os
#import zipfile
import shutil
import PyPDF2
import io
import pdf2image
from PIL import Image
from pytesseract import image_to_string
import sys
import re
import json
from flask import render_template, Flask, request, make_response
from werkzeug import secure_filename
from werkzeug.datastructures import FileStorage
import cv2
import imutils
from imutils.object_detection import non_max_suppression
import numpy as np
import passport

app = Flask(__name__)

DEBUG = True

@app.route('/')
def index():
    return render_template('index.html')

class Page:
    def __init__(self, **kwargs):

        self.image = None
        self.filename = None
        self.text = None
        self.type = None
        self.end_file = None
        self.rotates = None
        if kwargs:
            self.__dict__.update(kwargs)

    def get_text(self):

        self.text = image_to_string(self.image, lang="rus")

    def is_passport(self):

        self.image = cv2.imread('tmp/{}'.format(self.filename))

        cascade = cv2.CascadeClassifier('cascade.xml')
        self.rotates = 0

        (h, w, d) = self.image.shape

        gray = cv2.cvtColor(self.image, cv2.COLOR_BGR2GRAY)

        for _ in range(4):

            faces = cascade.detectMultiScale(gray, 1.3, 5)
            if faces is not ():
                return True

            gray = imutils.rotate_bound(gray, 90)
            self.rotates += 1

        return False

class Scanner:

    FILE_END = [
        "(подпись)",
    ]

    STATUTE = {
        'rights': ['общество вправе', "общество обладает", "Общество может"],
        'authority': ["органами управления общества", "органам управления общества"],
        'term': ['директор общества принимается', "срок полномочий", "директор .{0,60}назначается", "срок полномочий", 'Директор .{0,60}избирается'],
        "powers": ['директор .{0,20} осуществляет .{0,20} полномочия:', 'директор .{0,60}общества:'],
        "limits": ['директор .{0,20} не вправе', 'не вправе'],
        'technical': r'[а-я \n,“"\':;\d]*)\.?;?',
    }

    RENT = {
        'adress': ['по адресу:'],
        'time': ['срок аренды помещения:'],
        'landlord': ['арендодатель'],
        'technical': r'[а-я \n,“"\':;\d]*\.?;?',
    }

    TREATY = {
        "header": ["юридические адреса", "реквизиты сторон", "подписи сторон"],
        "role": ['арендодатель', "субарендодатель", "арендатор", "субарендатор", 'исполнитель', 'заказчик', 'поставщик', 'покупатель'],
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
    "treaty": ["договор поставки", "договор субаренды", "договор указания.{0, 25}услуг"],
    "statute": ["деятельности общества", "статус общества", \
        "капитал общества", "участника общества", "выход участника из общества", \
        "распределение прибыли", "фонды общества", "собрание участников"],
    "others": ["информационная карта", "отчет", "заявление", "опись", "заключение", "лицензия", "свидетельство"],
    }

    def __init__(self, path, file_name):

        global STATUS
        STATUS = 'Conerting to PNG'

        self.files = []
        self.documents = []


        if file_name.endswith('.pdf'):
            pages = self._convert_to_image(path, file_name, format='PDF')

        if file_name.endswith('.tif') or file_name.endswith('.tiff'):
            pages = self._convert_to_image(path, file_name, format='TIF')


        if not os.path.exists('tmp'):
            os.mkdir('tmp')
        if not os.path.exists('text'):
            os.mkdir('text')


        name = 0
        for page in pages:
            page.image.save(os.path.join('tmp', '{}.png'.format(name)))
            page.filename = '{}.png'.format(name)
            self.files.append(page)
            name += 1


        """
        for name in os.listdir('text'):
            with open('text/{}'.format(name), 'r') as f:
                text = f.read()
            page = Page(text=text)
            page.type = self._define_type(page)
            self.files.append(page)

        self.documents = [self.files]
        """

    def prepare(self):

        name = 0
        for file in self.files:
            global STATUS
            STATUS = 'Procesing {} file'.format(name)

            file.get_text()
            with open('text/{}.txt'.format(name), 'w') as f:  # Used for testing as well
                f.write(file.text)
            file.type = self._define_type(file)
            name += 1
            for match in self.FILE_END:
                if re.search(match, file.text, flags=re.I):
                    file.end_file = True

        if len(self.files) > 15:
            self.documents = self._divide_into_documents()
        else:
            self.documents.append(self.files)

    def analyze(self):

        answer = []
        global STATUS
        STATUS = 'Analyzing document'

        for document in self.documents:
            doc = {}
            type_ = self._document_type(document)
            if type_ == 'statute':
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
                doc['parties'] = self.analyze_treaty(document)
            elif type_ == 'balance':
                doc['type'] = 'balance'
            elif type_ == 'passport':
                doc['type'] = 'passport'
                doc['context'] = self._analyze_passport(document)
            elif type_ == "treaty":
                context = self.analyze_treaty(document)

                doc['type'] = 'treaty'
                doc['context'] = context
            if doc != {}:
                answer.append(doc)

        return answer

    def _convert_to_image(self, path, file_name, format=None):
        if format is None:
            return None

        elif format == 'PDF':
            pages = list()
            images = pdf2image.convert_from_path(file_name)
            if not os.path.exists('tmp'):
                os.mkdir('tmp')

            name = 0
            for img in images:
                img.save('tmp/{}.png'.format(name))
                pages.append(Page(image=img))
                name += 1
            return pages

        elif format == 'TIF':
            pages = list()
            img = Image.open(file_name)
            if not os.path.exists('tmp'):
                os.mkdir('tmp')

            for i in range(100):
                try:
                    img.seek(i)
                except EOFError:
                    break

                try:
                    img.save('tmp/{}.png'.format(i))
                    temp = Image.open('tmp/{}.png'.format(i))
                    pages.append(Page(image=temp))
                except Exception:
                    pass

            # TODO
            return pages

    def _define_type(self, file):

        text = file.text

        for doc_type in self.MATCHES.keys():
            for match in self.MATCHES[doc_type]:
                if re.search(match, text, flags=re.I):
                    if doc_type == 'others':
                        return 'others/{}'.format(match)
                    return doc_type

        if file.is_passport():
            return 'passport'

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

    def _document_type(self, document):

        potential_types = {}
        for page in document:
            if page.type is None:
                page.type = 'NotDefined'
            else:
                if page.type not in potential_types.keys():
                    potential_types[page.type] = 0
                potential_types[page.type] += 1

        inverse = [(value, key) for key, value in potential_types.items()]

        print(inverse)
        return max(inverse)[1]


    def _analyze_statute(self, document):

        for page in document:
            text += page.text

        rights = []
        for match in self.STATUTE['rights']:
            right = re.search(r'({}{}'.format(match, self.STATUTE['technical']), text, flags=re.I)
            if right:
                rights.append(right.group(0))

        authority = []
        for match in self.STATUTE['authority']:
            authority_ = re.search(r'({}{}'.format(match, self.STATUTE['technical']), text, flags=re.I)
            if authority_:
                authority.append(authority_.group(0))

        term = []
        for match in self.STATUTE['term']:
            term_ = re.search(r'({}{}'.format(match, self.STATUTE['technical']), text, flags=re.I)
            if term_:
                term.append(term_.group(0))

        powers = []
        for match in self.STATUTE['powers']:
            power = re.search(r'({}{}'.format(match, self.STATUTE['technical']), text, flags=re.I)
            if power:
                powers.append(power.group(0))

        limits = []
        for match in self.STATUTE['limits']:
            limit = re.search(r'({}{}'.format(match, self.STATUTE['technical']), text, flags=re.I)
            if limit:
                limits.append(limit.group(0))

        return (rights, authority, term, powers, limits)



    def analyze_treaty(self, document):

        text = ''
        for page in document:
            text += page.text

        TREATY = {
            "header": ["юридические адреса", "реквизиты сторон", "подписи сторон"],
            "role": ['арендодатель', "субарендодатель", "арендатор", "субарендатор", 'исполнитель', 'заказчик', 'поставщик', 'покупатель'],
        }

        result = {}
        result['party1'] = {'Название':'', 'Роль':'', 'ИНН': '', "ОГРН": ''}
        result['party2'] = {'Название':'', 'Роль':'', 'ИНН': '', "ОГРН": ''}


        for header in self.TREATY['header']:
            if re.search(header, text, flags=re.I):

                text = re.search(r'({}.*)'.format(header), text, flags=re.I | re.DOTALL)[1]

                if len(text) > 800:
                    text = text[:800]


            if re.search(r' (\d{10})( |\n)', text):
                result['party1']['ИНН'] = re.findall(r' (\d{10})( |\n|/)', text)[0][0]
                result['party2']['ИНН'] = re.findall(r' (\d{10})( |\n|/)', text)[1][0]

            if re.search(r' (\d{13})(\n| )', text):
                result['party1']['ОГРН'] = re.findall(r' (\d{13})(\n| )', text)[0][0]
                result['party2']['ОГРН'] = re.findall(r' (\d{13})(\n| )', text)[1][0]


            for role in self.TREATY['role']:
                if re.search(role, text, flags=re.I):
                    result['party1']['Роль'] = re.findall(r'{}'.format(role), text, flags=re.I)[0]

                    request = role + '.{150}'
                    name_area = re.findall(request, text, flags=re.I | re.DOTALL)[0]
                    result['party1']['Название'] = re.findall(r'(.{0,10}(«|").{0,30}(»|"))' , name_area, flags=re.I)[0][0]
                    break

            for role in self.TREATY['role']:
                if re.search(role, text, flags=re.I) and role != result['party1']['Роль'].lower():
                    result['party2']['Роль'] = re.findall(r'{}'.format(role), text, flags=re.I)[0]

                    if len(re.findall(r'(.{0,10}(«|").{0,30}(»|"))', name_area, flags=re.I)) >= 2:
                        result['party2']['Название'] = re.findall(r'(.{0,10}(«|").{0,30}(»|"))', name_area, flags=re.I)[1][0]
                    else:
                        request = role + '.{150}'
                        name_area = re.findall(request, text, flags=re.I | re.DOTALL)[0]
                        result['party1']['Название'] = re.findall(r'(.{0,10}(«|").{0,30}(»|"))', name_area, flags=re.I)[0][0]

                    break

            result['raw'] = text
            return result

    def _analyze_rent(self, document):

        text = ''

        for page in document:
            text += page.text

        adress = ''
        for match in self.RENT['adress']:
            if re.search(r'\n.*\n.*{}.*\n.*\n'.format(match), text, flags=re.I):
                adress = re.search(r'(\n.*\n.*{}.*\n.*\n)'.format(match), text, flags=re.I)
                adress = adress.group(0)
                break

        time = ''
        for match in self.RENT['time']:
            if re.search(r'{}{}'.format(match, self.RENT['technical']), text, flags=re.I):
                time = re.search(r'({}{})'.format(match, self.RENT['technical']), text, flags=re.I)
                time = time.group(0)
                break

        landlord = ''
        for match in self.RENT['landlord']:
            if re.search(r'\n.*\n.*{}.*\n.*\n'.format(match), text, flags=re.I):
                company = re.search(r'(\n.*\n.*{}.*\n.*\n)'.format(match), text, flags=re.I)
                landlord = company.group(0)
                break

        return (adress, time, landlord)


    def _analyze_passport(self, document):

        text = ''

        for page in document:
            image = cv2.imread('tmp/{}'.format(page.filename))
            image = imutils.rotate_bound(image, 90 * page.rotates)
            cv2.imwrite('tmp/{}'.format(page.filename), image)

            print('foo')
            image = cv2.imread('tmp/{}'.format(page.filename))
            """
            cv2.imshow('test', image)
            cv2.waitKey(0)
            """
            text += passport.read_data_from_passport(image)

        return text


META_DATA = {'data': []}
STATUS = 'doesnt work'

@app.route('/uploader', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':

        META_DATA['data'] = []
        files = request.files.getlist('file')
        archive = request.files['file']

        if archive.filename.endswith('.zip'):
            files = unzip(archive.filename)

        for f in files:
            analyze_document(f)

        return json.dumps(META_DATA, ensure_ascii=False)


def analyze_document(f):

    f.save(f.filename)

    scanner = Scanner('', f.filename)
    scanner.prepare()
    result = scanner.analyze()[0]

    #answer = json.dumps(result, ensure_ascii=False)
    global STATUS
    STATUS = 'doesnt work'
    META_DATA['data'].append(result)


def unzip(file_name):

    with zipfile.ZipFile(file_name, 'r') as zip_ref:
        zip_ref.extractall()

        files = []
        for f in zip_ref.infolist():
            files.append(f)
        return files

@app.route('/results', methods=['GET'])
def return_results():
    return json.dumps(META_DATA, ensure_ascii=False)


@app.route('/status', methods=['GET'])
def return_status():
    return STATUS


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
