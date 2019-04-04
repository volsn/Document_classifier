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
from flask import render_template, Flask, request, make_response
from werkzeug import secure_filename

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
        if kwargs:
            self.__dict__.update(kwargs)

    def get_text(self):

        self.text = image_to_string(self.image, lang="rus")


class Scanner:

    FILE_END = [
        "(подпись)",
    ]

    STATUTE = {
        'rights': ['общество вправе', "общество обладает", "Общество может"],
        'authority': ["УПРАВЛЕНИЕ ОБЩЕСТВОМ", 'органами общества', "органами управления общества", "органом общества", \
                                                                           "органам управления общества"],
        'term': ['директор общества принимается', "срок полномочий", "директор назначается", "срок полномочий", 'Директор избирается'],
        "powers": ['директор [а-я ]{0,20} осуществляет [а-я ]{0,20} полномочия:', 'директор [а-я ]{0,60}общества:'],
        "limits": ['директор [а-я ]{0,20} не вправе', 'не вправе'],
        'technical': r'[а-я \n,“"\':;\d]*)\.?;?',
    }

    RENT = {
        'adress': ['по адресу:'],
        'time': ['срок аренды помещения:'],
        'landlord': ['“арендодатель”'],
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
        self.documents = []

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
        if not os.path.exists('text'):
            os.mkdir('text')

        """
        For test purpose
        """
        name = 0
        for page in pages: 
            page.image.save(os.path.join('tmp', '{}.png'.format(name)))
            page.filename = '{}.png'.format(name)
            self.files.append(page)
            name += 1

    def prepare(self):

        name = 0
        for file in self.files:
            file.get_text()
            with open('text/{}.txt'.format(name), 'w') as f:  # Used for testing as well
                f.write(file.text)
            file.type = self._define_type(file.text)
            name += 1
            for match in self.FILE_END:
                if re.search(match, file.text, flags=re.I):
                    file.end_file = True

        if len(self.files) > 8:
            self.documents = self._divide_into_documents()
        else:
            self.documents = [self.files]

    def analyze(self):
        answer = []

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
            elif type_ == 'balance':
                doc['type'] = 'balance'
            else:
                pass

            if doc != {}:
                answer.append(doc)

        print(answer)

        return answer

    def _unzip(self, path, file_name):
        with zipfile.ZipFile(os.path.join(path, file_name), 'r') as zip_ref:
            zip_ref.extractall(path)

    def _convert_to_image(self, path, file_name, format=None):
        if format is None:
            return None
        
        elif format == 'PDF':
            pages = list()
            images = pdf2image.convert_from_path(file_name, dpi=200, fmt="png")
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

    def _document_type(self, document):

        potential_types = {}
        for page in document:
            if page.type is None:
                page.type = 'NotDefined'
            if page.type not in potential_types.keys():
                potential_types[page.type] = 0
            potential_types[page.type] += 1

        inverse = [(value, key) for key, value in potential_types.items()]
        print(inverse)
        return max(inverse)[1]


    def _analyze_statute(self, document):

        text = ''

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

    def _analyze_rent(self, document):

        text = ''

        for page in document:
            text += page.text

        adress = ''
        for match in self.RENT['adress']:
            if re.search(r'{} [а-я .,\n0-9/]*[^кв.м]?[^(]?'.format(match), text, flags=re.I):
                adress = re.search(r'{} [а-я .,\n0-9/]*[^кв.м]?[^(]?'.format(match), text, flags=re.I)
                adress = adress.group(0)
                break

        time = ''
        for match in self.RENT['time']:
            if re.search(r'{} [а-я 0-9]*[^.(/\\]'.format(match), text, flags=re.I):
                time = re.search(r'{} ([а-я 0-9]*[^.(/\\])'.format(match), text, flags=re.I)
                time = time.group(0)
                break
        
        landlord = ''
        for match in self.RENT['landlord']:
            if re.search(r'(«[а-я-\s]*»)?(«[а-я-\s]*»)?[()/\\,.а-я\s]*{}'.format(match), text, flags=re.I):
                company = re.search(r'(«[а-я-\s]*»)?(«[а-я-\s]*»)?[()/\\,.а-я\s]*{}'.format(match), text, flags=re.I)
                landlord = company.group(0)
                break 

        return (adress, time, landlord)


@app.route('/uploader', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        f = request.files['file']
        f.save(f.filename)

        scanner = Scanner('', f.filename)
        scanner.prepare()
        result = scanner.analyze()

        resp = make_response()
        resp.headers['Result'] = result

        return resp



if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
