import json
import socket
from run_client import *
from config import Types_Server


def connection():
    SERVER = "127.0.0.1"
    PORT = 4003
    ADDR = (SERVER, PORT)
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(ADDR)
    check(client)


def check(client):
    reg = registration()
    client.sendall(bytes(reg, encoding='utf-8'))
    msg_accepted = receive(client)
    if msg_accepted["type"] == Types_Server.ERR:  # в случае ошибки
        print(msg_accepted["text"])
        check(client)
    elif msg_accepted["type"] == Types_Server.LIST:  # все ок, авторизация прошла
        run(client, msg_accepted)


def registration():
    while True:
        clientText = input('Введите 0 для регистрации \n'
                           'Введите 1 для авторизации: ')
        if clientText == Types_Client.REG or clientText == Types_Client.AUTH:
            login = input("Введите логин: ")
            password = input("Введите пароль: ")
            msg = {
                'type': clientText,
                'login': login,
                'pass': password
            }
            return json.dumps(msg)
        else:
            print('Что-то вы не то ввели!')
