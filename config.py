import os
from environs import Env

env = Env()
env.read_env()

groupname = env.str("groupname")
groupid = env.int("groupid")
groupsyn = env.str("groupsyn")
token_group = env.str("token_group")
admin_id = env.int("admin_id")
admin_pass = env.str("admin_pass")
admin_phone = env.str("admin_phone")
chat_for_suggest = '2000000001'
group_hashtags = [
    ['#Парикмахеры@beautiful_sortirovka',
     '#Визажисты@beautiful_sortirovka',
     '#Массажисты@beautiful_sortirovka',
     '#Косметологи@beautiful_sortirovka',
     '#НогтевойСервис@beautiful_sortirovka',
     '#НовостиГруппы@beautiful_sortirovka'],
    ['#Ресницы@beautiful_sortirovka',
     '#Брови@beautiful_sortirovka',
     '#Ботокс@beautiful_sortirovka',
     '#ВыпрямлениеВолос@beautiful_sortirovka',
     '#НаращиваниеВолос@beautiful_sortirovka'],
    ['#НаращиваниеНогтей@beautiful_sortirovka',
     '#Шугаринг@beautiful_sortirovka',
     '#Депиляция@beautiful_sortirovka',
     '#Эпиляция@beautiful_sortirovka',
     '#Пирсинг@beautiful_sortirovka',
     '#Тату@beautiful_sortirovka']
]


def getConfig():
    serverconfig = {'groupname': groupname,
                    'groupsyn': groupsyn,
                    'group_token': token_group,
                    'admin_id': admin_id,
                    'admin_phone': admin_phone,
                    'admin_pass': admin_pass,
                    'group_id': groupid,
                    'chat_for_suggest': chat_for_suggest,
                    'available_hashtags': get_available_hashtags(group_hashtags),
                    'group_hashtags': group_hashtags}
    return serverconfig


def get_available_hashtags(hashtag_list):
    hashtags = []
    for hashtag in hashtag_list:
        if isinstance(hashtag, list):
            hashtags.extend(get_available_hashtags(hashtag))
        else:
            hashtags.append(hashtag)
    return hashtags