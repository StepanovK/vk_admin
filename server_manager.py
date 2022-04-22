import time
import config
from datetime import datetime

from server import Server


serverconfig = config.getConfig()
server1 = Server(serverconfig.get('groupname', ''), serverconfig)

while True:
    try:
        server1.start()
    except Exception as err:
        print(err)
        print('\n{}: Переподключение к серверам ВК'.format(datetime.now()))
        time.sleep(3)
