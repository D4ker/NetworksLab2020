import os
import json
import socket
import threading
import time
from math import sqrt
from datetime import datetime
from math import factorial

HEADER = 4096
SERVER_WORKING = True
SERVER_CLOSE = False
HOST = "127.0.0.1"  # ip сервера (localhost)
# HOST = "0.0.0.0"
PORT = 4003  # порт

TYPES = {
    # Сокращения для типов пакетов сервера
    "SRV": {
        "LST": "0",  # Список тестов
        "QST": "1",  # Следующий вопрос
        "RSL": "2",  # Результат последнего теста
        "DSC": "3",  # Отключить пользователя
        "ERR": "4",  # Ошибка
    },
    # Сокращения для типов пакетов клиента
    "CLT": {
        "REG": "0",  # Регистрация
        "AUT": "1",  # Авторизация
        "LST": "2",  # Список тестов
        "RES": "3",  # Результат последнего теста
        "TST": "4",  # Получить тест
        "ANS": "5",  # Ответ на вопрос
        "DSC": "6"  # Отключиться от сервера
    }
}

ERRORS = {
    # User is exists
    "UIE": {
        "code": "0",
        "msg": "Такой пользователь уже существует."
    },
    # Wrong login or password
    "WLP": {
        "code": "1",
        "msg": "Неверное имя пользователя или пароль."
    },
    # Result not exist
    "RNE": {
        "code": "3",
        "msg": "Вы пока не писали ни одного теста."
    },
    # Test not exist
    "TNE": {
        "code": "4",
        "msg": "Теста с таким номером не существует."
    }
}

# Путь к папке с файлами
DIR = "files/"

clients = {}  # адреса и данные (!) подключенных клиентов

def serverTime():
    return datetime.timestamp(datetime.now())

def serverTimeFormat(mytime):
    return datetime.strftime(datetime.fromtimestamp(mytime + time.timezone), "%Y-%m-%d-%H.%M.%S")

def printLog(time, message):
    print(f"[{serverTimeFormat(time)}]/[log]: {message}")

# Получить JSON из файла ***
def getJSONfromFile(fileName):
    with open(DIR + fileName, "r", encoding="utf-8") as jsonFile:
        return json.load(jsonFile)

# Перезаписать JSON в файл ***
def setJSONtoFile(fileName, jsonData):
    with open(DIR + fileName, "w", encoding="utf-8") as jsonFile:
        json.dump(jsonData, jsonFile, ensure_ascii=False, indent=4)

# Создать список тестов и их UID (файл list.json) ***
def createList():
    # https://stackabuse.com/reading-and-writing-json-to-a-file-in-python/
    data = {}

    for file in os.listdir(DIR):
        if file.endswith(".json"):
            uid = file[:len(file) - 5]
            if uid.isdigit():
                name = getJSONfromFile(file)["name"]
                data[uid] = name

    setJSONtoFile("list.json", data)

# Функция для отключения клиента от сервера ***
def disconnect(client):
    addres = client.getsockname()
    clients.pop(client)
    client.close()
    leftmsg = f"[{addres[0]}:{str(addres[1])}] -> DISCONNECT"
    printLog(serverTime(), leftmsg)

# Отключить всех от сервера ***
def disconnectAll():
    global SERVER_CLOSE
    global SERVER_WORKING
    global server

    SERVER_CLOSE = True
    print("---Server Stopped---")
    if clients:
        for client in list(clients):
            # Если пользователь был авторизован - отключить безопасно. Иначе - отключить сразу
            if "login" in clients[client]:
                sendDisconnect(client)
            else:
                disconnect(client)
    else:
        SERVER_WORKING = False
        server.close()
        exit(0)

# Распарсить команду, введённую администратором
def parseCommand(command):
    commandList = command.split(" ")

    if commandList[0] == 'disconnect' and commandList[1]:
        return {
            "type": 0,
            "login": commandList[1]
        }
    elif commandList[0] == 'stop':
        return {
            "type": 1,
        }

    return {
        "type": -1
    }

# Отправляем пользователю пакет с ошибкой ***
def sendError(client, error):
    code = error["code"]
    msg = error["msg"]

    jsonPacket = {
        "type": TYPES["SRV"]["ERR"],
        "code": code,
        "text": msg
    }

    packet = bytes(json.dumps(jsonPacket), encoding="utf-8")
    client.sendall(packet)

# Отправляем пользователю пакет со списком тестов ***
def sendList(client):
    # Получаем список всех тестов с их UID и названиями
    jsonData = getJSONfromFile("list.json")

    jsonPacket = {
        "type": TYPES["SRV"]["LST"],
        "list": jsonData
    }

    packet = bytes(json.dumps(jsonPacket, ensure_ascii=False, indent=4), encoding="utf-8")
    client.sendall(packet)

# Отправить результат последнего теста ***
def sendResult(client):
    # Получаем список всех пользователей
    jsonData = getJSONfromFile("users.json")
    lastTest = jsonData["clients"][clients[client]["login"]]["last_test"]

    jsonPacket = {
        "type": TYPES["SRV"]["RSL"],
        "name": lastTest["name"],
        "result": lastTest["result"]
    }

    packet = bytes(json.dumps(jsonPacket, ensure_ascii=False, indent=4), encoding="utf-8")
    client.sendall(packet)

# Отправить следующий вопрос ***
def sendQuestion(client):
    # Вытаскиваем из массива первый вопрос и сохраняем ответ на вопрос
    question = clients[client]["questions"].pop(0)
    clients[client]["answer"] = question["correct_answer"]

    jsonPacket = {
        "type": TYPES["SRV"]["QST"],
        "question": question["question"],
        "answers": question["answers"]
    }

    packet = bytes(json.dumps(jsonPacket, ensure_ascii=False, indent=4), encoding="utf-8")
    client.sendall(packet)

# Отправить запрос на отключение пользователя от сервера ***
def sendDisconnect(client):
    # Мы отключаем клиента, а не он от нас
    clients[client]["online"] = False

    # Отправляем пакет на отключение клиента
    jsonPacket = {
        "type": TYPES["SRV"]["DSC"]
    }

    packet = bytes(json.dumps(jsonPacket, ensure_ascii=False, indent=4), encoding="utf-8")
    client.sendall(packet)

# Регистрация ***
def regRequest(client, packet):
    # Получаем список всех пользователей
    jsonData = getJSONfromFile("users.json")
    users = jsonData["clients"]

    # Если такой пользователь уже существует - отправляем ошибку
    if packet["login"] in users:
        sendError(client, ERRORS["UIE"])
        return

    # Иначе - добавляем пользователя и отправляем список тестов
    jsonData["clients"][packet["login"]] = {
        "pass": packet["pass"],
        "last_test": {
            "name": "",
            "result": "-1"
        }
    }

    setJSONtoFile("users.json", jsonData)

    # Запоминаем, что пользователь успешно авторизовался (его ник)
    clients[client]["login"] = packet["login"]
    clients[client]["online"] = True

    sendList(client)

# Авторизация ***
def authRequest(client, packet):
    # Получаем список всех пользователей
    jsonData = getJSONfromFile("users.json")

    # Если такой пользователь существует и пароль правильный - авторизация успешна
    if packet["login"] in jsonData["clients"] and packet["pass"] == jsonData["clients"][packet["login"]]["pass"]:
        # Запоминаем, что пользователь успешно авторизовался (его ник)
        clients[client]["login"] = packet["login"]
        clients[client]["online"] = True

        # Отправляем список тестов авторизованному пользователю
        sendList(client)
        return

    # Иначе - отправляем ошибку
    sendError(client, ERRORS["WLP"])

# Запрос результата последнего теста ***
def resultRequest(client):
    # Получаем список всех пользователей
    jsonData = getJSONfromFile("users.json")

    lastTest = jsonData["clients"][clients[client]["login"]]["last_test"]

    # Если пользователь ещё не писал ни один тест - отправить ошибку
    if lastTest["result"] == "-1":
        sendError(client, ERRORS["RNE"])
        return

    sendResult(client)

# Запрос теста по UID ***
def testRequest(client, packet):
    # Получаем тест
    jsonData = getJSONfromFile(packet["number"] + ".json")

    # Сохраняем имя теста, массив вопросов теста, размер этого массива и обнуляем значение текущих правильных ответов
    clients[client]["test_name"] = jsonData["name"]
    clients[client]["questions"] = jsonData["questions"]
    clients[client]["questions_size"] = len(jsonData["questions"])
    clients[client]["correct_answers"] = 0

    sendQuestion(client)

# Ответ на вопрос ***
def answerResponse(client, packet):
    if packet["answer"] == clients[client]["answer"]:
        clients[client]["correct_answers"] += 1

    # Если список вопросов уже пустой, значит предыдущий вопрос был последним - отправить результат
    if not clients[client]["questions"]:
        result = clients[client]["correct_answers"] / clients[client]["questions_size"] * 100

        # Получаем список всех пользователей
        jsonData = getJSONfromFile("users.json")

        # Сохраняем имя и результат (нормированный, в процентах) последнего теста
        jsonData["clients"][clients[client]["login"]]["last_test"] = {
            "name": clients[client]["test_name"],
            "result": "{:.2f}".format(result)
        }
        setJSONtoFile("users.json", jsonData)

        # Отправляем результат
        sendResult(client)
        return

    # Иначе - отправить следующий вопрос
    sendQuestion(client)

# Запрос на отключение ***
def disconnectRequest(client):
    global SERVER_CLOSE
    global SERVER_WORKING
    global server

    # Если пользователь послал запрос на отключение - отправить ему ответ
    if clients[client]["online"] is True:
        sendDisconnect(client)

    # Мы получили от пользователя ответ на его принудительное отключение от нашего сервера. Отключаем его
    disconnect(client)

    # Если список клиентов пустой и сейчас происходит остановка сервера
    if not clients and SERVER_CLOSE is True:
        SERVER_WORKING = False
        server.close()
        exit(0)

# Функция для работы с клиентом. Получаем сообщения и обрабатываем их
def handle(client):
    try:
        while SERVER_WORKING:
            # Получаем пакет с информацией, что нужно клиенту от сервера
            packet = json.loads(client.recv(HEADER).decode("utf-8"))
            print(packet)

            typeOp = packet["type"]

            if typeOp == 1 or typeOp == 0:
                op = packet["operation"]
                ans = 0.0
                if op < 4:
                    if op == 0:
                        ans = packet["arg"][0] + packet["arg"][1]
                    if op == 1:
                        ans = packet["arg"][0] - packet["arg"][1]
                    if op == 2:
                        ans = packet["arg"][0] * packet["arg"][1]
                    if op == 3:
                        ans = packet["arg"][0] / packet["arg"][1]
                elif op == 4:
                    ans = factorial(packet["arg"][0])
                else:
                    ans = sqrt(packet["arg"][0])

                jsonPacket = {
                    "type": 0,
                    "answer": ans,
                    "id": packet["id"]
                }

                packet = bytes(json.dumps(jsonPacket, ensure_ascii=False, indent=4), encoding="utf-8")
                client.sendall(packet)
                continue


    except (ConnectionResetError):
        # Сработает также в случае, когда клиент отключится с помощью ctrl + c
        print("AAAAA213")
        disconnect(client)
    except:
        pass

# Функция для обработки подключения пользователей к серверу
def receive(server):
    global SERVER_WORKING
    try:
        while SERVER_WORKING:
            client, addres = server.accept()
            printLog(serverTime(), f"Connected with {str(addres)}")

            clients[client] = {}

            thread = threading.Thread(target=handle, args=(client,))
            thread.start()

    except KeyboardInterrupt:
        disconnectAll()

# Функция для ввода команд сервером
def write():
    global SERVER_WORKING
    try:
        while SERVER_WORKING:
            commandList = None
            while commandList == None:
                # disconnect user
                # stop
                command = input("")
                commandList = parseCommand(command)

                typeCmd = commandList["type"]
                if typeCmd == 0:
                    keys = clients.keys()
                    for client in keys:
                        if "login" in clients[client] and clients[client]["login"] == commandList["login"]:
                            sendDisconnect(client)
                            break
                    # print("Ошибка: Этот пользователь в данный момент не подключен к серверу")
                elif typeCmd == 1:
                    disconnectAll()
                else:
                    print("Ошибка: Неизвестная команда")

    except KeyboardInterrupt:
        disconnectAll()

# Для обеспечения правильного поведения консоли (при закрытии) ***
def on_exit(sig, func=None):
    print("exit handler")
    time.sleep(10)  # so you can see the message before program exits

# Запуск сервера с созданием списка тестов, а также выделением потоков для команд и ожидания пользователей ***
def startServer():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))

    server.listen()

    # Поток для ввода команд сервером
    writeThread = threading.Thread(target=write)
    writeThread.start()

    # Поток для получения данных от клиентов
    receive(server)

# Запускаем сервер
startServer()