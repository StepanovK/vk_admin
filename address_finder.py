from selenium import webdriver
import time
import os


def main():
    print(get_address_info('', True))


def get_address_info(address: str, test_mode=False):
    if test_mode:
        current_dir = os.getcwd()
        current_dir = current_dir.replace('\\', '/')
        url = 'file://' + current_dir + '/TestPage/index.html'
    else:
        url = get_map_url(address)
    print("Оперделение координат на странице: " + url)
    driver = get_webdriver(test_mode)
    driver.get(url)
    time.sleep(3)
    errors = []
    coords = get_coords_from_driver(driver, errors)
    full_address = get_address_from_driver(driver, errors)
    full_address = address if full_address == '' else full_address
    short_address = get_short_address_from_driver(driver, errors)
    short_address = address if short_address == '' else short_address
    return {'coords': coords, 'address': full_address, 'short_address': short_address, 'errors': errors}


def get_webdriver(test_mode=False):
    options = webdriver.ChromeOptions()
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--incognito')
    if not test_mode:
        options.add_argument('--headless')
    current_dir = os.getcwd()
    path = r"{}\chromedriver.exe".format(current_dir)
    return webdriver.Chrome(options=options, executable_path=path)


def get_map_url(address: str):
    map_url = 'https://yandex.ru/maps/?source=serp_navig&text={}'
    return map_url.format(address)


def get_coords_from_driver(map_page: webdriver, errors: list):
    div_coords = map_page.find_element_by_class_name('toponym-card-title-view__coords-badge')
    text_coords = '' if div_coords is None else div_coords.text
    text_coords = text_coords.replace('\n', '')
    coords = text_coords.split(', ')
    float_coords = 0, 0
    text_error = ''
    if len(coords) == 2:
        try:
            float_coords = float(coords[0]), float(coords[1])
        except:
            text_error = """Не удлось определить координаты\n
                         div_coords: {}\n
                         text_coords: "{}" """.format(div_coords, text_coords)
            print(text_error)
            errors.append(text_error)
    # print(float_coords)
    return float_coords


def get_address_from_driver(map_page: webdriver, errors: list):
    meta_property = map_page.find_element_by_xpath("//meta[@property='og:title']")
    text_address = ''
    try:
        text_address = '' if meta_property is None else str(meta_property.get_property("content"))
        text_address = text_address.strip()
    except:
        text_error = """Не удлось определить координаты\n
                     meta_property: {}\n
                     text_address: "{}" """.format(meta_property, text_address)
        print(text_error)
        errors.append(text_error)
    # print(text_address)
    return text_address


def get_short_address_from_driver(map_page: webdriver, errors: list):
    cardtitle = map_page.find_element_by_xpath("//h1[@class='card-title-view__title'][@itemprop='name']")
    text_address = ''
    try:
        text_address = '' if cardtitle is None else str(cardtitle.text)
        text_address = text_address.strip()
    except:
        text_error = """Не удлось определить координаты\n
                      cardtitle: {}\n
                      text_address: "{}" """.format(cardtitle, text_address)
        print(text_error)
        errors.append(text_error)
    # print(text_address)
    return text_address


if __name__ == '__main__':
    main()
    # print(get_address_info('Ленина 1'))