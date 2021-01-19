import json
import socket
import threading
import time

HEADER = 4096
CLIENT_WORKING = True
SERVER_IP = "127.0.0.1"
# SERVER_IP = "51.15.130.137"
SERVER_PORT = 7777

# Типы пакетов
TYPES = {
    # Сокращения для типов пакетов сервера
    "SRV": {
        "ANS": 0,  # Ответ сервера
    },
    # Сокращения для типов пакетов клиента
    "CLT": {
        "QCK": 0,  # Быстрая операция
        "LNG": 1,  # Долгая операция
    }
}

# Типы операций
opString = "+-*/"
FACT = 4
SQRT = 5

# Идентификатор данных, отправляемых пользователем
id = 0

# Словарь для хранения данных, введённых пользователем
data = {}

# Отключение от сервера ***
def disconnect(client):
    global CLIENT_WORKING

    if CLIENT_WORKING:
        print("Вы были отключены от сервера")
        CLIENT_WORKING = False
        client.close()
        exit(0)

# Отправка пакета на сервер ***
def sendPacket(client, packetDict, strCmd):
    global id

    packetDict["id"] = id
    data[id] = strCmd

    id = id + 1
    packet = bytes(json.dumps(packetDict), encoding="utf-8")
    client.sendall(packet)

# Ответ на вопрос ***
def answerResponse(packet):
    answerID = packet['id']
    print(f"id: {answerID}\nОтвет: {data[answerID]} = {packet['answer']}")

# Функция для обработки информации, приходящей с сервера ***
def receive(client):
    global CLIENT_WORKING
    try:
        while CLIENT_WORKING:
            # Получаем пакет с информацией от сервера
            packet = json.loads(client.recv(HEADER).decode("utf-8"))

            # Для демонстрации пакета, приходящего с сервера
            print(packet)

            typeOp = packet["type"]

            # Сначала проверяем, авторизован ли уже пользователь (ведь login есть только у авторизованных)
            if typeOp == TYPES["SRV"]["ANS"]:
                answerResponse(packet)

    except (ConnectionAbortedError, ConnectionResetError, ValueError):
        disconnect(client)

# Вспомогательная функция для чисел с плавающей запятой ***
def is_digit(string):
    if string.isdigit():
       return True
    else:
        try:
            float(string)
            return True
        except ValueError:
            return False

# Парсинг команды ***
def parseCommand(command):
    commandList = command.split(" ")
    commandLength = len(commandList)

    if commandLength == 3:
        x = commandList[0]
        y = commandList[2]
        op = commandList[1]
        # Первый и последний аргументы - числа, между ними - один символ, который также находится в строке opString
        if is_digit(x) and is_digit(y) and len(op) == 1 and op in opString:
            return {
                "type": 0,
                "operation": opString.index(op),
                "arg": [float(x), float(y)]
            }
    elif commandLength == 2:
        x = commandList[1]
        op = commandList[0]
        if is_digit(x):
            if op == "fact":
                opCode = FACT
            elif op == "sqrt":
                opCode = SQRT
            else:
                return {"type": -1}
            return {
                "type": 1,
                "operation": opCode,
                "arg": [float(x)]
            }
    elif commandLength == 1:
        if commandList[0] == "disconnect":
            return {"type": 2}
    return {"type": -1}

# Печать в консоль всех доступных операций ***
def printHelp():
    print("Команды:")
    print("1. Сумма: <arg1> + <arg2>")
    print("2. Разность: <arg1> - <arg2>")
    print("3. Умножение: <arg1> * <arg2>")
    print("4. Деление: <arg1> / <arg2>")
    print("5. Факториал: fact <arg>")
    print("6. Квадратный корень: sqrt <arg>")

# Функция для написания команд ***
def write(client):
    global CLIENT_WORKING
    try:
        # Печатаем в консоль все доступные операции
        printHelp()
        while CLIENT_WORKING:
            # operation
            command = input("")
            commandDict = parseCommand(command)

            typeCmd = commandDict["type"]
            if typeCmd == TYPES["CLT"]["QCK"] or typeCmd == TYPES["CLT"]["LNG"]:
                sendPacket(client, commandDict, command)
            elif typeCmd == 2:
                disconnect(client)
                break
            else:
                print("Ошибка: Неизвестная команда")

    except (KeyboardInterrupt, EOFError):
        disconnect(client)

# Запуск клиента с выделением потоков для команд и ожидания пользователей ***
def startClient():
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    ip = input("Введите IP (по умолчанию: 127.0.0.1): ")
    port = input("Введите PORT (по умолчанию: 7777): ")

    # Если выбраны ip и port по умолчанию
    if not ip:
        ip = SERVER_IP

    if not port:
        port = SERVER_PORT
    elif port.isdigit():
        port = int(port)

    try:
        client.connect((ip, port))
    except ConnectionRefusedError:
        print(f"Server ({ip}:{port}) is not available")
        exit(0)

    # Поток для ввода команд клиентом
    writeThread = threading.Thread(target=write, args=(client,))
    writeThread.start()

    # Поток для получения данных от сервера
    receive(client)

# Запускаем клиент
startClient()
