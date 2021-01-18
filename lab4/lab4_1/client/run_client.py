import json

from config import *


def run(client, tests):
    while True:
        #print("{} - просмотр всех тестов \n".format(COMMAND[0]) +
        #      "{} - показ последнего пройденного теста \n".format(COMMAND[1]) +
        #      "{} - выбрать тест \n".format(COMMAND[2]) +
        #      "{} - выход".format(COMMAND[3]))
        command = input("Выберете команду: ")
        if command == COMMAND[0]:
            get_list(tests)
        elif command == COMMAND[1]:
            get_result(client)
        elif command == COMMAND[2]:
            choice = choose_test(tests)
            run_testing(client, choice)
        elif command == COMMAND[3]:
            disconnect_client(client)
            break
        else:
            print("Некорректная команда")


def get_list(msg_accepted):
    for key in msg_accepted["list"]:
        print(key, ":", msg_accepted["list"][key])


def get_result(client):
    msg = {
        "type": Types_Client.RESULT
    }
    msg = json.dumps(msg)
    request(client, msg)
    result = receive(client)
    if result["type"] == Types_Server.ERR:
        print(result["text"])
    else:
        print(result["name"])
        print(result["result"])


def choose_test(msg_accepted):
    while True:
        number = input("Выберете тест (формат: номер теста):")
        if number not in msg_accepted["list"]:
            print("Такого теста нет(, выберите заново")
        else:  # формируем сообщение для получения 1 вопроса
            msg = {
                "type": Types_Client.TEST,
                "number": number
            }
            return json.dumps(msg)


def run_testing(client, choice):
    request(client, choice)
    test = receive(client)
    while True:
        if test["type"] == Types_Server.NEXT_QRT:
            msg = answer_to(test)
            request(client, msg)
            test = receive(client)
        elif test["type"] == Types_Server.RESULT:
            print(test["name"])
            print(test["result"])
            break


def answer_to(test):
    while True:
        print(test["question"])
        for i in test["answers"]:
            print(i)
        answer = input("Выберете вариант ответа (формат: отсчет начинается с 0!):")
        if int(answer) in [i for i in range(len(test["answers"]))]:
            print('ответ получен!')
            msg = {
                "type": Types_Client.ANSWER,
                "answer": answer
            }
            msg = json.dumps(msg)
            return msg
        else:
            print('такого варианта вообще-то нет!'
                  ' Отвечай заново!')


def disconnect_client(client):  # клиент решил отключиться
    msg = {
        "type": Types_Client.DISCONNECT
    }
    msg = json.dumps(msg)
    request(client, msg)
    result = receive_disconnect(client)
    if result["type"] == Types_Server.DISCONNECT:
        client.shutdown()
        client.close()
        exit()


def request(client, msg):
    client.sendall(bytes(msg, encoding='utf-8'))


def receive(client_socket):
    msg = json.loads(client_receive(client_socket).decode('utf-8'))
    print(msg)
    if msg["type"] == Types_Server.DISCONNECT:
        disconnect_server(client_socket)
    return msg

def receive_disconnect(client_socket):
    return json.loads(client_receive(client_socket).decode('utf-8'))

def client_receive(current_socket):
    return current_socket.recv(4096)


def disconnect_server(client):  # сервер решил отключить клиента
    msg = {
        "type": Types_Client.DISCONNECT
    }
    msg = json.dumps(msg)
    request(client, msg)
    client.shutdown()
    client.close()
    exit()
