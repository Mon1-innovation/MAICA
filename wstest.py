#!/usr/bin/python
# -*- coding: UTF-8 -*-


import json
import time
from websocket import create_connection


class WSClient:
    def __init__(self, address):
        self.ws = create_connection(address)

    def send(self, params):
        print("Sending ...")
        self.ws.send(params)
        print("Sending Data: {}".params)
        print("Reeiving...")
        result = self.ws.recv()
        print("Received '{}'".format(result))

    def quit(self):
        self.ws.close()


t = str(time.time() * 1000).split(".")[0]


params1 = """
oD/Ro1FNmlgN7e4BBGdzm77T0LkN263yiz+wRUsWFEu8tQA94rPetuo0Rd/RmzSrnRX/PusBCj8pUMoAQCv1FqeYEcZTpWmYE8gn/UMw1qvmXDKPEH2kacwam4BTk0S6iZo00isc0Ag20spm4ZzNm3iw950sCEzphpS/sJc0XWTdmYblYrsmw9R+kCAWdESaw+mM1SXBxoa4LVZK6VNFdtwqdM5MGHb70h0o9H40JTxFuAX/NYj9mksmivSGOHqaRuW8dS0qYm9gMF8+a2CIq4iatlbHFrk5rZPC/eJ4HjO1trNp/lZhZsnc7rFUliWwEYOxgSLCWVOUWtiQn/C1Sg==
"""
params2 = '{"model": "maica_core", "sf_extraction": False}'

if __name__ == '__main__':

    address = "wss://maicadev.monika.love/websocket"

    # 初始化
    web_client = WSClient(address)
    web_client.send(params1)
    web_client.send(params2)
    while True:
        msg = input('params:')
        web_client.send(msg)

    # 断开连接
    web_client.quit()
    print(r'send end')
