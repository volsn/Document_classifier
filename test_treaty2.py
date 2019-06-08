import re
import os
import cv2
import imutils
from pytesseract import image_to_string
from PIL import Image

TREATY = {
    "header": ["юридические адреса", "реквизиты сторон", "подписи сторон"],
    "role": ['арендодатель', "субарендодатель", "арендатор", "субарендатор", 'исполнитель', 'заказчик', 'поставщик', 'покупатель'],
}

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

def init_document(path_img='tmp', path_text='text'):

    images = os.listdir(path_img)
    texts = os.listdir(path_text)
    images.sort()
    texts.sort()

    document = []
    for img_file, text_file in zip(images, texts):

        img = cv2.imread(os.path.join(path_img, img_file), 0)

        with open(os.path.join(path_text, text_file)) as f:
            text = f.read()
        """
        # For testing purpose
        text = image_to_string(img, lang='rus')
        name = img_file.split('.')[0]
        with open(os.path.join(path_text, '{}.txt'.format(name)), 'w') as f:
            f.write(text)
        """

        # print(img_file)

        document.append(Page(
            text = text,
            image = img,
            filename = img_file,
        ))

    return document

def find_footer(document):

    """
    # TODO  document[0].image
    """
    first_page = cv2.imread('tmp/0.png', 0)
    (h, w) = first_page.shape
    first_page = first_page[0:int(h/4), 0:w]

    first_page_text = image_to_string(first_page, lang='rus')

    for i, page in enumerate(document):
        for match in TREATY['header']:
            if re.search(match, page.text, flags=re.I):

                docs = document[i:]

                text_both = ''
                text_one = ''
                text_two = ''

                for j, page_ in enumerate(docs):

                    text_both += page_.text

                    img = page_.image
                    (h, w) = img.shape

                    party1 = img[0:h, 0:int(w/2)]
                    party2 = img[0:h, int(w/2):w]

                    if not os.path.exists('divided'):
                        os.mkdir('divided')

                    cv2.imwrite(os.path.join('divided', '{}1.png'.format(j)), party1)
                    cv2.imwrite(os.path.join('divided', '{}2.png'.format(j)), party2)

                    party1 = image_to_string(party1, lang='rus')
                    party2 = image_to_string(party2, lang='rus')

                    text_one += party1
                    text_two += party2

                """
                if len(text_both) > 800:
                    text_both = re.search('{}.*'.format(match), text_both, flags=re.I)[0]
                if len(text_one) > 500:
                    text_one = text_one[:500]
                if len(text_two) > 500:
                    text_two = text_two[:500]
                """

                return (text_both, text_one, text_two, first_page_text)


def analyze_treaty(text, text_one, text_two, text_first_page):

    result = {}
    result['party1'] = {'Название':[], 'Роль':[], 'ИНН': '', "ОГРН": '', 'адрес': '', 'подписант': ''}
    result['party2'] = {'Название':[], 'Роль':[], 'ИНН': '', "ОГРН": '', 'адрес': '', 'подписант': ''}

    result['raw'] = text_one + text_two

    names_first_page = re.findall(r'((ООО|ОАО|АО).{0,3}(«|").{0,30}(»|"))' , text_first_page, flags=re.I)

    names_cleaned = []
    temp_names = []
    for name in names_first_page:
        temp = re.search(r'(«|")(.{0,30})(»|")', name[0])[0]

        if temp not in temp_names:
            temp_names.append(temp)
            names_cleaned.append(name[0])

    if names_cleaned:
        result['party1']['Название'].append(names_cleaned[0])
    if len(names_cleaned) >= 2:
        result['party2']['Название'].append(names_cleaned[1])

    for role in TREATY['role']:
        if re.search(role, text_first_page, flags=re.I):
            result['party1']['Роль'].append(re.search(role, text_first_page, flags=re.I)[0])
            break

    for role in TREATY['role']:
        if re.search(role, text_first_page, flags=re.I) and role != result['party1']['Роль'][0].lower():
            result['party2']['Роль'].append(re.search(role, text_first_page, flags=re.I)[0])
            break

    inn1 = re.search(r' (\d{10})( |\n)', text_one)
    inn2 = re.search(r' (\d{10})( |\n)', text_two)

    if inn1:
        result['party1']['ИНН'] = inn1[0].replace('\n', '').replace(' ', '')
    if inn2:
        result['party2']['ИНН'] = inn2[0].replace('\n', '').replace(' ', '')

    ogrn1 = re.search(r' (\d{13})(\n| )', text_one)
    ogrn2 = re.search(r' (\d{13})(\n| )', text_two)

    if ogrn1:
        result['party1']['ОГРН'] = ogrn1[0].replace('\n', '').replace(' ', '')
    if ogrn2:
        result['party2']['ОГРН'] = ogrn2[0].replace('\n', '').replace(' ', '')


    for role in TREATY['role']:
        if re.search(role, text_one, flags=re.I):
            result['party1']['Роль'] = re.search(r'{}'.format(role), text_one, flags=re.I)[0]

            request = role + '.{150}'
            name_area = re.search(request, text_one, flags=re.I | re.DOTALL)[0]
            name = re.search(r'((ООО|ОАО|АО).{0,3}(«|").{0,30}(»|"))', name_area, flags=re.I)
            if name:
                result['party1']['Название'].append(name[0])
            break

    for role in TREATY['role']:
        if re.search(role, text_two, flags=re.I):
            result['party2']['Роль'] = re.search(r'{}'.format(role), text_two, flags=re.I)[0]

            request = role + '.{150}'
            name_area = re.search(request, text_two, flags=re.I | re.DOTALL)[0]
            name = re.search(r'((ООО|ОАО|АО).{0,3}(«|").{0,30}(»|"))' , name_area, flags=re.I)
            if name:
                result['party2']['Название'].append(name[0])
            break


    rs1 = re.search(r'р/с:.{0,3}(\d{20})', text_one, flags=re.I)
    if rs1:
        result['party1']['р/с'] = rs1[0].replace('\n', '').replace(' ', '')

    rs2 = re.search(r'р/с:.{0,3}(\d{20})', text_two, flags=re.I)
    if rs2:
        result['party1']['р/с'] = rs2[0].replace('\n', '').replace(' ', '')

    adress1 = re.search(r'(Юридический адрес.{0,100})(Фактический|ИНН|р/с|ОГРН)', text_one, flags=re.I | re.DOTALL)
    if adress1:
        result['party1']['адрес'] = adress1[0].replace('\n', '')

    adress2 = re.search(r'(Юридический адрес.{0,150})(Фактический|ИНН|р/с|ОГРН)', text_two, flags=re.I | re.DOTALL)
    if adress2:
        result['party2']['адрес'] = adress2[0].replace('\n', '')


    # Looking for signer

    sign1 = re.search('/({0, 20})/', text_one, flags=re.I)
    if sign1:
        result['party1']['подписант'] = sign1[0]
    else:
        sign1 = re.findall(r'([А-Я]{4,15}.{0,2}[А-Я]{1}\.[А-Я]{1}\.)', text_one, flags=re.I)

        if sign1:
            signs = []
            for sign in sign1:
                signs.append(sign)
            signs.sort(key=len)

            result['party1']['подписант'] = signs[-1]
            result['all_names'] = signs

    sign2 = re.search('/({0, 20})/', text_two, flags=re.I)
    if sign2:
        result['party2']['подписант'] = sign2[0]
    else:
        sign2 = re.findall(r'([А-Я]{4,15}.{0,2}[А-Я]{1}\.[А-Я]{1}\.)', text_two, flags=re.I)

        if sign2:
            signs = []
            for sign in sign2:
                if sign != result['party1']['подписант']:
                    signs.append(sign)
            signs.sort(key=len)

            result['party2']['подписант'] = signs[-1]


    if result['party2']['ИНН'] == '' and result['party2']['ОГРН'] == '':

        if re.search(r' (\d{10})( |\n)', text):
            inn = re.findall(r' (\d{10})( |\n|/)', text)
            if len(inn) >= 2:
                result['party2']['ИНН'] = [1][0]

        if re.search(r' (\d{13})(\n| )', text):
            ogrn = re.findall(r' (\d{13})(\n| )', text)
            if len(ogrn) >= 2:
                result['party2']['ОГРН'] = ogrn[1][0]


        for role in TREATY['role']:
            if re.search(role, text, flags=re.I):
                first_party_role = re.findall(r'{}'.format(role), text, flags=re.I)[0]

                request = role + '.{150}'
                name_area = re.findall(request, text, flags=re.I | re.DOTALL)[0]
                result['party1']['Название'] = re.findall(r'((ООО|ОАО|АО).{0,3}(«|").{0,30}(»|"))' , name_area, flags=re.I)[0][0]
                break

        for role in TREATY['role']:
            if re.search(role, text, flags=re.I) and role != first_party_role.lower():
                result['party2']['Роль'] = re.findall(r'{}'.format(role), text, flags=re.I)[0]

                if len(re.findall(r'((ООО|ОАО|АО).{0,3}(«|").{0,30}(»|"))', name_area, flags=re.I)) >= 2:
                    result['party2']['Название'] = re.findall(r'((ООО|ОАО|АО).{0,3}(«|").{0,30}(»|"))', name_area, flags=re.I)[1][0]
                else:
                    request = role + '.{150}'
                    name_area = re.findall(request, text, flags=re.I | re.DOTALL)[0]
                    result['party1']['Название'] = re.findall(r'((ООО|ОАО|АО).{0,3}(«|").{0,30}(»|"))', name_area, flags=re.I)[0][0]

                break

        adresses = re.findall(r'(Юридический адрес.{0,150})Фактический|ИНН|р/с|ОГРН', text, flags=re.I | re.DOTALL)
        if adresses:
            result['party1']['адрес'] = adresses[0]
        if len(adresses) >= 2:
            result['party2']['адрес'] = adresses[1]

    return result
