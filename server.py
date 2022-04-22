import json
import random
import threading
import schedule
import os
import time
from datetime import datetime
import address_finder

import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType

from vk_messages import MessagesAPI


def get_str_attachments_from_post(post):
    attachments = ''
    if 'attachments' in post and post['attachments']:
        attachments_array = []
        for attach in post['attachments']:
            if attach["type"] != 'link':
                new_attach = attach["type"] + str(
                    attach[attach["type"]]['owner_id']) + '_' + str(
                    attach[attach["type"]]['id'])
                attachments_array.append(new_attach)
        attachments = ','.join(attachments_array)
    return attachments


def clear_cookies(login):
    del_file(f'cookies_vk_auth_{login}.pickle')
    del_file('vk_config.v2.json')


def del_file(filename):
    if os.path.exists(filename):
        os.remove(filename)


def time_now():
    cur_time = datetime.now()
    return str(cur_time)[:19]

class Server:

    def __init__(self, server_name, serverconfig):

        self.server_name = server_name

        self.group_id = serverconfig['group_id']
        self.group_id_ = '-' + str(serverconfig['group_id'])
        self.chat_for_suggest = serverconfig['chat_for_suggest']
        self.groupname = serverconfig['groupname']
        self.groupsyn = serverconfig['groupsyn']

        self.vk = vk_api.VkApi(token=serverconfig['group_token'])
        self.longpoll = VkBotLongPoll(self.vk, serverconfig['group_id'], wait=55)
        self.vk = self.vk.get_api()

        self.admin_phone = serverconfig['admin_phone']
        self.admin_pass = serverconfig['admin_pass']
        self.connect_message_api()

        self.username = None
        self.answer = None
        self.vk_admin = vk_api.VkApi(serverconfig['admin_phone'], serverconfig['admin_pass'])
        self.vk_admin.auth()
        self.vk_admin = self.vk_admin.get_api()

        self.posts_settings = {}
        self.available_hashtags = serverconfig['available_hashtags']
        self.group_hashtags = serverconfig['group_hashtags']

    def start(self):

        self.start_threads()

        print('{}: Сервер запущен!'.format(time_now()))

        for event in self.longpoll.listen():

            if event.type == VkBotEventType.MESSAGE_NEW:
                print(event.object.message['text'])
                if event.from_user:
                    print('Написали в ЛС')
                elif event.from_chat:
                    if str(event.object['message']['peer_id']) == str(self.chat_for_suggest):
                        self.button_press_event_adminchat(event.object, self.chat_for_suggest)
                    reply_message = event.object['message'].get('reply_message')
                    geomessage_start_text = 'Для добавления геометки к посту ID:'
                    if (reply_message is not None
                            and reply_message['text'].find(geomessage_start_text) == 0):
                        main_post_text = reply_message['text']
                        main_post_text = main_post_text.replace(geomessage_start_text, '')
                        nearest_space = main_post_text.find(' ')
                        post_id = int(main_post_text[0:nearest_space])
                        geotags = None
                        errors = []
                        try:
                            geotags = address_finder.get_address_info(event.object['message']['text'])
                        except Exception as ex:
                            error = '{}: Ошибка получения геометки для поста ID {}: {}'.format(time_now(),
                                                                                             post_id,
                                                                                             ex)
                            print(error)
                            self.vk.messages.send(peer_id=self.chat_for_suggest,
                                                  message=error,
                                                  random_id=random.randint(10 ** 5, 10 ** 6))
                        if geotags is not None:
                            errors = geotags.get('errors', [])
                            if len(errors) > 0:
                                error = '{}: Ошибка получения геометки для поста ID {}: {}'.format(time_now(),
                                                                                                   post_id,
                                                                                                   '\n'.join(errors))
                                self.vk.messages.send(peer_id=self.chat_for_suggest,
                                                      message=error,
                                                      random_id=random.randint(10 ** 5, 10 ** 6))
                            self.add_geotag(post_id, geotags)
                            post = self.get_post(post_id)
                            if post is None:
                                print('Не найден пост c ID ' + str(post_id))
                            else:
                                user = self.get_user(post['user_id'])
                                message = 'Для поста ID:{} от {} ' \
                                          'добавлена метка адреса:\n {}'.format(post_id,
                                                                                user.get('chat_name'),
                                                                                geotags.get('address'))
                                self.vk.messages.send(peer_id=self.chat_for_suggest,
                                                      message=message,
                                                      random_id=random.randint(10 ** 5, 10 ** 6))


            elif event.type == VkBotEventType.WALL_POST_NEW:
                obj = event.obj
                print('{}: Новый пост:'.format(time_now()))
                print(obj)
                if obj['post_type'] == 'suggest':
                    post_id = obj['id']
                    post = self.get_post(post_id)
                    if post is None:
                        print('Не найден пост c ID ' + str(post_id))
                    else:
                        user = self.get_user(post['user_id'])
                        self.send_msg(random.randint(10 ** 5, 10 ** 6), self.chat_for_suggest,
                                      ('Новый пост от {} в предложке:\n'
                                       + '{}\n'
                                       + 'текст:\n'
                                       + '{}{}').format(user['chat_name'],
                                                        self.get_post_link(post_id),
                                                        post['text'],
                                                        self.get_text_last_posts(post['user_id'], 3)),
                                      keyboard=self.get_keyboard("keyboards/new_post.json", post_id),
                                      attachment=post['attachments'])
            else:
                print('{}: Новое событие {}:'.format(time_now(), event.type))
                print(event)

    def start_threads(self):
        scheduler_thread_name = self.server_name + '_start_scheduler'
        if not self.thread_is_alive(scheduler_thread_name):
            scheduler_thread = threading.Thread(target=self.start_scheduler,
                                                name=scheduler_thread_name,
                                                args=())
            scheduler_thread.start()

    def thread_is_alive(self, thread_name):
        thread_is_alive = False
        for thread in threading.enumerate():
            if thread.name == thread_name:
                thread_is_alive = True
                # thread.isAlive()
                # thread_is_alive = thread.is_alive()
                break
        return thread_is_alive

    def start_scheduler(self):
        # schedule.every().day.at("04:00").do(self.connect_message_api)
        schedule.clear()
        schedule.every(12).hours.do(self.connect_message_api)
        while True:
            schedule.run_pending()
            time.sleep(1)

    def connect_message_api(self):
        login = self.admin_phone
        password = self.admin_pass
        clear_cookies(login)
        try:
            self.admin_messages = MessagesAPI(login, password, two_factor=False)
            print('{}: Соединение с АПИ сообщений установлено'.format(time_now()))
        except Exception as ex:
            print('{}: Ошибка соединения с АПИ сообщений: {}'.format(time_now(), ex))

    def send_msg(self, random_id, send_id, message, keyboard=None, attachment=None):

        #print("отправка сообщения " + message)

        if keyboard == None:
            keyboard = open("keyboards/none.json", "r", encoding="UTF-8").read()

        return self.vk.messages.send(peer_id=send_id,
                                     message=message,
                                     random_id=random_id,
                                     keyboard=keyboard,
                                     attachment=attachment)

    def get_keyboard(self, keyboard, post_id):
        #print(os.listdir("./"))
        keyboard = open(keyboard, "r", encoding="UTF-8").read()
        keyboard = json.loads(keyboard)
        for elem in keyboard['buttons']:
            elem[0]['action']['payload']["post_id"] = str(post_id)
        keyboard = json.dumps(keyboard, ensure_ascii=False)
        return keyboard

    def get_hashtag_keyboard(self, post_id, hashtag_group_number=1, number_of_columns=1, add_end_buttons=True):

        if number_of_columns == 0:
            raise ValueError("Неверно указано количество колонок хэштегов!")

        hashtags = []
        current_group = 1
        for hashtag in self.group_hashtags:
            if isinstance(self.group_hashtags, list) and current_group == hashtag_group_number:
                hashtags = hashtag
            elif isinstance(self.group_hashtags, str) and hashtag_group_number == 1:
                hashtags.append(hashtag)
            current_group += 1

        number_of_rows = len(hashtags) // number_of_columns
        current_index = 0
        if number_of_rows * number_of_columns < len(hashtags):
            number_of_rows += 1
        buttons = []
        for r in range(number_of_rows):
            row_of_buttons = []
            for c in range(number_of_columns):
                if current_index < len(hashtags):
                    button = {
                        "action": {
                            "type": "text",
                            "payload": {"command": 'add_hashtag',
                                        "post_id": str(post_id),
                                        "hashtag": hashtags[current_index]},
                            "label": hashtags[current_index]
                        },
                        "color": "default"
                    }
                    row_of_buttons.append(button)
                    current_index += 1
            buttons.append(row_of_buttons)
        if add_end_buttons:
            last_row = []
            clear_hashtags = {
                "action": {
                    "type": "text",
                    "payload": {"command": 'clear_hashtags',
                                "post_id": str(post_id)},
                    "label": "Удалить хэштеги"
                },
                "color": "negative"
            }
            last_row.append(clear_hashtags)
            public_post = {
                "action": {
                    "type": "text",
                    "payload": {"command": 'public_post',
                                "post_id": str(post_id)},
                    "label": "Закончить и опубликовать"
                },
                "color": "primary"
            }
            last_row.append(public_post)
            buttons.append(last_row)
        keyboard = {"one_time": False,
                    "inline": True,
                    "buttons": buttons}
        keyboard = json.dumps(keyboard, ensure_ascii=False)
        print(keyboard)
        return keyboard

    def get_reply_keyboard(self, post_id, from_group=True):

        reply_templates = self.get_reply_templates()

        answer_variants = reply_templates['answer_variants']
        number_of_columns = reply_templates['number_of_columns']

        if number_of_columns == 0:
            raise ValueError("Неверно указано количество колонок кнопок ответов!")

        number_of_rows = len(reply_templates['answer_variants']) // number_of_columns
        current_index = 0
        if number_of_rows * number_of_columns < len(answer_variants):
            number_of_rows += 1
        buttons = []
        for r in range(number_of_rows):
            row_of_buttons = []
            for c in range(number_of_columns):
                if current_index < len(answer_variants):
                    button = {
                        "action": {
                            "type": "text",
                            "payload": {"command": 'reply_to_user',
                                        "post_id": str(post_id),
                                        "from_group": str(int(from_group)),
                                        "reply_id": str(answer_variants[current_index]['reply_id'])},
                            "label": answer_variants[current_index]['label']
                        },
                        "color": "default"
                    }
                    row_of_buttons.append(button)
                    current_index += 1
            buttons.append(row_of_buttons)

        keyboard = {"one_time": False,
                    "inline": True,
                    "buttons": buttons}
        keyboard = json.dumps(keyboard, ensure_ascii=False)
        print(keyboard)
        return keyboard

    def get_reply_templates(self):
        reply_templates = open("keyboards/reply_templates.json", "r", encoding="UTF-8").read()
        reply_templates = json.loads(reply_templates)
        return reply_templates

    def reply_to_user(self, post_id, reply_id, from_group=True, enable_greeting=True):
        post = self.get_post(post_id)
        if post is None:
            print('Не найден пост c ID ' + str(post_id))
            return
        user_info = self.get_user(post['user_id'])
        if user_info['user_info_is_found'] == False:
            print('Не найден пользователь c ID ' + str(post['user_id']))

        reply_templates = self.get_reply_templates()
        message = ''
        for answer_variant in reply_templates.get('answer_variants', []):
            if answer_variant.get('reply_id', '') == reply_id:
                greeting = (
                    reply_templates.get('group_greeting') if from_group else reply_templates.get('admin_greeting'))
                greeting = (greeting + '\n') if enable_greeting else ''
                greeting = greeting.replace('groupname', str(self.groupname))
                greeting = greeting.replace('groupsyn', str(self.groupsyn))
                message = '{}{}\n' + 'ваш пост:\n' + '{}'
                message = message.format(greeting, answer_variant.get('text', ''), post['text'])
                break
        if len(message) > 0:
            if from_group:
                print('Отправка сообщения от имени группы пользователю {}'.format(user_info['id']))
                self.vk.messages.send(peer_id=user_info['id'],
                                      message=message,
                                      random_id=random.randint(10 ** 4, 10 ** 5),
                                      attachment=post['attachments'])
            else:
                print('Отправка сообщения от имени админа пользователю {}'.format(user_info['id']))
                # try:
                self.admin_messages.method('messages.send', user_id=user_info['id'],
                    message=message,
                    random_id=random.randint(10 ** 4, 10 ** 5),
                    attachment=post['attachments'])
                # elf.vk_admin.messages.send(peer_id=user_info['id'],
                #                             message=message,
                #                             random_id=random.randint(10 ** 4, 10 ** 5),
                #                             attachment=post['attachments'])
        self.vk.messages.send(peer_id=self.chat_for_suggest,
                              message='Сообщение отправлено. Текст: \n' + message,
                              random_id=random.randint(10 ** 4, 10 ** 5))

    def get_user(self, user_id):
        user_info = {
            'id': user_id,
            'first_name': '',
            'last_name': '',
            'photo_max': '',
            'last_seen': '',
            'city': '',
            'can_write_private_message': False,
            'online': False,
            'sex': '',
            'chat_name': '[id{}]'.format(user_id),
            'user_info_is_found': False
        }
        try:
            fields = 'id, first_name,last_name, photo_max, last_seen, city, can_write_private_message, online, sex'
            response = self.vk.users.get(user_ids=user_id, fields=fields)
            if isinstance(response, list) and len(response) > 0:
                user_info.update(response[0])
                city = user_info['city']
                user_info['city'] = city.get('title', '') if isinstance(city, dict) else city
                sex = user_info.get('sex', 0)
                user_info['sex'] = 'female' if sex == 1 else 'male' if sex == 2 else ''
                user_info['chat_name'] = '[id{}|{} {}]'.format(user_id,
                                                               user_info.get('last_name', ''),
                                                               user_info.get('first_name', ''))
                user_info['online'] = bool(user_info.get('online', 0))
                user_info['can_write_private_message'] = bool(user_info.get('can_write_private_message', 0))
                user_info['user_info_is_found'] = True
        except Exception as ex:
            print("Ошибка получения информации о пользователе: {0}".format(ex))
        return user_info

    def get_post_settings(self, post_id):
        settings = self.posts_settings.get(int(post_id))
        if settings is None:
            settings = {'hashtags': [],
                        'signed': 1,
                        'geotag': None}
            self.posts_settings[int(post_id)] = settings
        return settings

    def del_post_settings(self, post_id):
        if self.posts_settings.get(int(post_id)) is not None:
            self.posts_settings.pop(int(post_id))

    def get_post(self, post_id):
        found_post = None
        if post_id is not None and int(post_id) != 0:
            grouppost_id = self.group_id_ + '_' + str(post_id)
            posts = self.vk_admin.wall.getById(posts=grouppost_id)
            for post in posts:
                user_id = post['from_id']
                settings = self.get_post_settings(post_id)
                found_post = {"id": post_id, 'user_id': user_id, 'text': post['text'],
                              'attachments': get_str_attachments_from_post(post),
                              'hashtag': '\n'.join(settings['hashtags']), 'signed': settings['signed'],
                              'geotag': settings['geotag']}
        return found_post

    def get_text_last_posts(self, UserID, count=3):
        post_texts = []
        template = "{} от {}"
        for post in self.get_last_posts_from_user(UserID, count):
            timestamp = post['date']
            value = datetime.fromtimestamp(timestamp)
            date = value.strftime('%Y.%m.%d')
            post_texts.append(template.format(self.get_post_link(post['id']), date))
        start_text = '\nПоследние опубликованные посты автора:\n'
        return start_text + '\n'.join(post_texts) if len(post_texts) > 0 else ""

    def get_last_posts_from_user(self, UserID, count=5):
        all_posts = self.get_all_posts_from_user(UserID)
        sorted_posts = sorted(all_posts, key=lambda x: x['date'], reverse=True)
        last_posts = []
        for i in range(len(sorted_posts)):
            if i <= count-1:
                last_posts.append(sorted_posts[i])
            else:
                break
        return last_posts

    def get_all_posts_from_user(self, UserID):
        posts = []
        tools = vk_api.VkTools(self.vk_admin)
        all_posts = tools.get_all('wall.get', 100, {'owner_id': self.group_id_})
        for i in range(len(all_posts['items'])):
            post = all_posts['items'][i]
            if post.get('signer_id') == UserID:
                posts.append(post)
        return posts

    def set_signed(self, post_id, signed=1):
        settings = self.get_post_settings(post_id)
        settings['signed'] = signed
        self.posts_settings[int(post_id)] = settings

    def add_hashtag(self, post_id, hashtag):
        settings = self.get_post_settings(post_id)
        settings['hashtags'].append(hashtag)
        self.posts_settings[int(post_id)] = settings

    def clear_hashtags(self, post_id):
        settings = self.get_post_settings(post_id)
        settings['hashtags'] = []
        self.posts_settings[int(post_id)] = settings

    def add_geotag(self, post_id, geotag):
        settings = self.get_post_settings(post_id)
        settings['geotag'] = geotag
        self.posts_settings[int(post_id)] = settings

    def clear_geotag(self, post_id):
        settings = self.get_post_settings(post_id)
        settings['geotag'] = None
        self.posts_settings[int(post_id)] = settings

    def public_post(self, post_id):
        post = self.get_post(post_id)
        if post is None:
            print('Не найден пост c ID ' + str(post_id))
            return None
        else:
            message = post['text']
            if post['hashtag'] != '':
                message = message + '\n' + post['hashtag']
            lat = 0
            long = 0
            if post['geotag'] != None:
                lat = post['geotag']['coords'][0]
                long = post['geotag']['coords'][1]
            new_post = self.vk_admin.wall.post(owner_id=self.group_id_,
                                               signed=post['signed'],
                                               post_id=post_id,
                                               message=message,
                                               attachments=post['attachments'],
                                               lat=lat,
                                               long=long)
            self.del_post_settings(post_id)
            return new_post

    def delete_post(self, post_id):
        result = 0
        post = self.get_post(post_id)
        if post is None:
            print('Не найден пост c ID ' + str(post_id))
            return None
        else:
            result = self.vk_admin.wall.delete(owner_id=self.group_id_, post_id=post_id)
            self.del_post_settings(post_id)
        return result

    def get_post_link(self, post_id, use_short_link=True):
        link = ''
        if use_short_link:
            link_template = 'https://vk.com/wall{}_{}'
            link = link_template.format(self.group_id_, post_id)
        else:
            link_template = 'https://vk.com/public{}?w=wall{}_{}'
            link = link_template.format(self.group_id, self.group_id_, post_id)
        return link

    def button_press_event_adminchat(self, object, chat_id):

        payload = self.get_payload_from_button(object)

        if payload['command'] == "public_post":

            post_id = payload['post_id']

            if '[Анон]' in object.message['text']:
                self.set_signed(post_id, 0)

            new_post = self.public_post(post_id)

            message = ''
            if new_post is None:
                message = 'Пост с ID {} не был опубликован. Возможно, пост удалён.'.format(post_id)
            else:
                message = 'Пост с ID {} опубликован. {}'.format(
                    post_id, self.get_post_link(new_post['post_id']))
            self.vk.messages.send(peer_id=chat_id, message=message, random_id=random.randint(10 ** 5, 10 ** 6))

        elif payload['command'] == "reject":
            post_id = payload['post_id']
            result = self.delete_post(post_id)
            if result == 1:
                message = 'Пост с ID {} был удалён.'.format(post_id)
            else:
                message = 'Пост с ID {} НЕ был удалён! Возможно, пост не существует.'.format(post_id)
            self.vk.messages.send(peer_id=chat_id, message=message, random_id=random.randint(10 ** 5, 10 ** 6))

        elif payload['command'] == "add_hashtags":
            post_id = payload['post_id']
            self.print_hashtag_keyboard(post_id, chat_id)

        elif payload['command'] == "add_hashtag":
            post_id = payload['post_id']
            hashtag = payload['hashtag']
            self.add_hashtag(post_id, hashtag)

        elif payload['command'] == "clear_hashtags":
            post_id = payload['post_id']
            self.clear_hashtags(post_id)

        elif payload['command'] == "templates_to_reply_to_user":
            post_id = payload['post_id']
            self.print_reply_keyboard(post_id, chat_id)

        elif payload['command'] == "reply_to_user":
            post_id = payload['post_id']
            reply_id = payload['reply_id']
            from_group = bool(int(payload['from_group']))
            self.reply_to_user(post_id, reply_id, from_group)

        elif payload['command'] == "add_geotag":
            post_id = payload['post_id']
            post = self.get_post(post_id)
            if post is None:
                print('Не найден пост c ID ' + str(post_id))
            else:
                user = self.get_user(post['user_id'])
                message = 'Для добавления геометки к посту ID:{} от {} ' \
                          'напишите короткий адрес в ответ на это сообщение'.format(post_id,
                                                                                    user.get('chat_name'))
                self.vk.messages.send(peer_id=chat_id,
                                      message=message,
                                      keyboard=self.get_keyboard("keyboards/clear_geotag.json", post_id),
                                      random_id=random.randint(10 ** 5, 10 ** 6))

        elif payload['command'] == "clear_geotag":
            post_id = payload['post_id']
            self.clear_geotag(post_id)

        elif not payload['command'] is None:
                message = 'Неизвестная команда: {}'.format(payload['command'])
                self.vk.messages.send(peer_id=chat_id, message=message, random_id=random.randint(10 ** 5, 10 ** 6))
                print(message)

    def get_payload_from_button(self, button):
        payload = {}
        try:
            payload = eval(button['message']['payload'])
        except Exception:
            payload['command'] = None
            payload['post_id'] = ""
        return payload

    def print_hashtag_keyboard(self, post_id, chat_id):

        post = self.get_post(post_id)
        if post is None:
            message = 'Пост с ID {} не найден! Возможно, он был опубликован или удалён'.format(post_id)
            self.vk.messages.send(peer_id=chat_id,
                                  message=message,
                                  random_id=random.randint(10 ** 5, 10 ** 6), )
            return

        group_hashtags = self.group_hashtags
        is_lists_in_hashtags = False
        for i in range(len(group_hashtags)):
            if isinstance(group_hashtags[i], list):
                is_lists_in_hashtags = True
                break
        if not is_lists_in_hashtags:
            group_hashtags = [group_hashtags]

        user = self.get_user(post['user_id'])

        it_is_first_group = True
        for group_number in range(1, len(group_hashtags) + 1):
            keyboard = self.get_hashtag_keyboard(post_id, group_number, 3, group_number == len(group_hashtags))
            message = 'ещё хэштеги'
            if it_is_first_group:
                message = 'Выберите хэштеги для поста ID {} от {}:\n{}'.format(
                    post_id,
                    post['user_id'],
                    user['chat_name'],
                    post['text'])
                it_is_first_group = False
            self.vk.messages.send(peer_id=chat_id,
                                  message=message,
                                  random_id=random.randint(10 ** 5, 10 ** 6),
                                  keyboard=keyboard)

    def print_reply_keyboard(self, post_id, chat_id):
        post = self.get_post(post_id)
        if post is None:
            message = 'Пост с ID {} не найден! Возможно, он был опубликован или удалён'.format(post_id)
            self.vk.messages.send(peer_id=chat_id,
                                  message=message,
                                  random_id=random.randint(10 ** 5, 10 ** 6), )
            return

        user_info = self.get_user(post['user_id'])
        if user_info['user_info_is_found'] == False:
            message = 'Не найдена информация о пользователе с ID {}'.format(post['user_id'])
            print(message)
            self.vk.messages.send(peer_id=chat_id,
                                  message=message,
                                  random_id=random.randint(10 ** 5, 10 ** 6), )

        elif self.user_has_groupchat(user_info['id']):
            message = 'Выберите подходящий ответ пользователю {}. ' \
                      '(Ответ будет отправлен от имени группы)'.format(user_info['chat_name'])
            self.send_msg(random.randint(10 ** 5, 10 ** 6), chat_id,
                          message,
                          keyboard=self.get_reply_keyboard(post_id, True))
        elif user_info.get('can_write_private_message', False):
            message = 'Выберите подходящий ответ пользователю {}. ' \
                      '(Ответ будет отправлен от имени админа)'.format(user_info['chat_name'])
            self.send_msg(random.randint(10 ** 5, 10 ** 6), chat_id,
                          message,
                          keyboard=self.get_reply_keyboard(post_id, False))
        else:
            message = 'Нет способа связи с пользователем {}. ' \
                      '(В группу не писал, ЛС закрыты)'.format(user_info['chat_name'])
            self.vk.messages.send(peer_id=chat_id,
                                  message=message,
                                  random_id=random.randint(10 ** 5, 10 ** 6), )

    def user_has_groupchat(self, user_id):
        user_has_groupchat = False
        words = ['Начать', 'Привет', 'Здравствуйте', 'Почему', 'Рекламу', 'Мой', 'Пост']
        for word in words:
            user_has_groupchat = self.user_has_message_in_the_chat(user_id, word)
            if user_has_groupchat:
                break
        return user_has_groupchat

    def user_has_message_in_the_chat(self, user_id, text, find_in_group=True):
        message_found = False
        try:
            messages = []
            if find_in_group:
                messages = self.vk.messages.search(q=text, peer_id=str(user_id), group_id=self.group_id)
            else:
                messages = self.vk_admin.messages.search(q=text, peer_id=str(user_id), group_id=self.group_id)
            if isinstance(messages, int):
                print(("При проверке наличия сообщений пользователя {} возникла ошибка с кодом {}."
                       + "\n Проверка в чатах с группой = {}").format(user_id, messages, find_in_group))
                messages = []
            elif not isinstance(messages, dict) or not ('items' in messages and isinstance(messages['items'], list)):
                print(("При проверке наличия сообщений пользователя {} возникла ошибка."
                       + "\n Результат поиска сообщений имеет неизвестный формат:"
                       + "\n {}"
                       + "\n Проверка в чатах с группой = {}").format(user_id, messages, find_in_group))
                messages = []

            message_found = isinstance(messages, dict) and 'count' in messages and int(messages['count']) > 0
        except:
            print("Неизвестная ошибка при проверки наличия сообщений пользователя {}".format(user_id))
        return message_found

