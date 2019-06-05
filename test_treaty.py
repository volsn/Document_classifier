import re

text = ''
with open('8.txt', 'r') as f:
    text += f.read()



TREATY = {
    "header": ["юридические адреса", "реквизиты сторон", "подписи сторон"],
    "role": ['арендодатель', "субарендодатель", "арендатор", "субарендаторы", 'Исполнитель', 'заказчик', 'ПОСТАВЩИК', 'покупатель'],
}

result = {}
result['party1'] = {'Название':'', 'Роль':'', 'ИНН': '', "ОГРН": ''}
result['party2'] = {'Название':'', 'Роль':'', 'ИНН': '', "ОГРН": ''}


for header in TREATY['header']:
    if re.search(header, text, flags=re.I):

        text = re.search(r'({}.*)'.format(header), text, flags=re.I | re.DOTALL)[1]

        if len(text) > 800:
            text = text[:800]

        break

if re.search(r' (\d{10})( |\n)', text):
    result['party1']['ИНН'] = re.findall(r' (\d{10})( |\n)', text)[0][0]
    result['party2']['ИНН'] = re.findall(r' (\d{10})( |\n)', text)[1][0]

if re.search(r' (\d{13})(\n| )', text):
    result['party1']['ОГРН'] = re.findall(r' (\d{13})(\n| )', text)[0][0]
    result['party2']['ОГРН'] = re.findall(r' (\d{13})(\n| )', text)[1][0]


for role in TREATY['role']:
    if re.findall(role, text, flags=re.I):
        result['party1']['Роль'] = re.findall(role, text, flags=re.I)[0]
        #text = re.search(role + ':(.{100})', text, flags=re.I | re.DOTALL)[0]
for role in TREATY['role']:
    if re.findall(role, text, flags=re.I) \
                and role != result['party1']['Роль']:
        result['party2']['Роль'] = re.findall(role, text, flags=re.I)[1]


name = re.search(r'(.{0,5}\«.{0,20}\»)', text, flags=re.I)

print(result['party2'])

"""
for role in TREATY['role']:

    if re.search(r'({}:)'.format(role), text, flags=re.I):

        text = re.search(r'({}:.*)'.format(role), text, flags=re.I | re.DOTALL)[1]
        print(len(text))


        name = re.search(r'(.{0,10}\"|«.{0,150}\»|")', text, flags=re.I)
        role = re.search(r'{} .\{50}', text, flags=re.I)
        role = re.search(r'(.{0,15}):', text, flags=re.I)

        result['party1']['Роль'] = role[0]
        result['party1']['Роль'] = role[1]

        result['party1']['Название'] = name[0]
        result['party2']['Название'] = name[1]

    result['party1']['ИНН'] = re.search(r'\d{10} ', text)
    result['party2']['ИНН'] = re.search(r'\d{10} ', text)

    result['party1']['ОГРН'] = re.search(r'\d{13} ', text)
    result['party2']['ОГРН'] = re.search(r'\d{13} ', text)

print(result['party1']['Название'])
"""
