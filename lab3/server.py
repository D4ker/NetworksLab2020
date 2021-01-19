import os
import selectors
import socket
import struct
import time
from datetime import datetime

HEADER = 600
SERVER_WORKING = True
HOST = "127.0.0.1"  # ip сервера (localhost)
# HOST = "0.0.0.0"
PORT = 4004  # порт

RRQ = 1
WRQ = 2
DATA = 3
ACK = 4
ERROR = 5

OCTET_MODE = 'octet'

ERRORS = {
    "ND": {
        "code": 0,
        "msg": "Unknown error."
    },
    "FNF": {
        "code": 1,
        "msg": "File not found."
    },
    "ITO": {
        "code": 4,
        "msg": "Illegal TFTP operation."
    },
    "FAE": {
        "code": 6,
        "msg": "File already exists."
    }
}

server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server.bind((HOST, PORT))

#server.setblocking(False)
sel = selectors.DefaultSelector()

clients = {}  # адреса и данные (!) подключенных клиентов

def serverTime():
    return datetime.timestamp(datetime.now())

def serverTimeFormat(mytime):
    return datetime.strftime(datetime.fromtimestamp(mytime + time.timezone), "%Y-%m-%d-%H.%M.%S")

def printLog(time, message):
    print(f"[{serverTimeFormat(time)}]/[log]: {message}")

# Вспомогательная функция для закрытия файла, если он был открыт
def closeFile(client):
    if 'file' in clients[client]:
        clients[client]['file'].close()
        del clients[client]['file']

# Функция для отключения клиента от сервера
def disconnect(client):
    clients.pop(client)
    leftmsg = f"[{client[0]}:{str(client[1])}] -> DISCONNECT"
    printLog(serverTime(), leftmsg)

# Функция для отправки блока данных клиенту
def sendData(client, blockNum):
    # Считываем из файла следующие 512 байт
    blockData = clients[client]['file'].read(512)
    packet = struct.pack(f"!HH{len(blockData)}s", DATA, blockNum, blockData)

    clients[client]['block_num'] = blockNum
    clients[client]['block_data'] = blockData

    server.sendto(packet, client)

# Функция для отправки ACK клиенту
def sendAck(client, blockNum):
    packet = struct.pack(f"!HH", ACK, blockNum)
    clients[client]['block_num'] = blockNum
    server.sendto(packet, client)

# Функция для отправки ошибки клиенту
def sendError(client, error):
    code = error["code"]
    msg = error["msg"]
    packet = struct.pack(f"!HH{len(msg)}sx", ERROR, code, bytes(msg, "ascii"))
    disconnect(client)
    server.sendto(packet, client)

# Функция для отправки нестандартной ошибки клиенту
def sendErrorWithMsg(client, msg):
    error = {
        "code": ERRORS["ND"]["code"],
        "msg": msg
    }
    sendError(client, error)

# Функция для обработки RRQ запроса
def readRequest(client, packetEnd):
    try:
        fileAndMode = packetEnd.split(b'\x00')
        fileName = fileAndMode[0].decode("ascii")
        mode = fileAndMode[1].decode("ascii")
        clients[client]['file_mode'] = mode
        print(fileName)
        print(mode)

        if mode == OCTET_MODE:
            # Сохраняем открытый файл, из которого будем считывать информацию по 512 байт
            clients[client]['file'] = open(fileName, 'rb')

            blockNum = 1
            sendData(client, blockNum)
        else:
            print("Error: Mode Not Found")
    except FileNotFoundError:
        print("Error: FileNotFoundError")
        closeFile(client)

        # Отправляем ошибку клиенту (файл отсутствует на сервере)
        sendError(client, ERRORS["FNF"])

# Функция для обработки WRQ запроса
def writeRequest(client, packetEnd):
    fileAndMode = packetEnd.split(b'\x00')
    fileName = fileAndMode[0].decode("ascii")
    mode = fileAndMode[1].decode("ascii")
    print(fileName)
    print(mode)
    print(client)
    print(f"\nCLIENTS:    {clients}")

    try:
        if os.path.exists(fileName):
            print("Error. File Is Exists")

            # Отправляем ошибку клиенту (файл уже есть)
            sendError(client, ERRORS["FAE"])
        else:
            # Сохраняем открытый файл, в который будем записывать информацию по 512 байт
            clients[client]['file'] = open(fileName, 'xb')

            blockNum = 0
            clients[client]['file_name'] = fileName
            clients[client]['file_mode'] = mode
            if mode != OCTET_MODE:
                print("Error: Mode Not Found")
            sendAck(client, blockNum)
    except ValueError:
        print("Error path")

        # Отправляем ошибку клиенту
        msg = "Illegal path."
        sendErrorWithMsg(client, msg)

# Функция для обработки DATA ответа
def dataResponse(client, packetEnd):
    (strBlockNum,), blockData = struct.unpack("!H", packetEnd[:2]), packetEnd[2:]
    blockNum = int(strBlockNum)
    oldBlockNum = clients[client]['block_num']
    # Пришёл повторный кусок данных, а значит клиент не получил наш ACK
    if oldBlockNum == blockNum:
        sendAck(client, blockNum)
    elif oldBlockNum + 1 == blockNum:
        print(f"BLOCK = {blockNum}")
        clients[client]['file'].write(blockData)

        if len(blockData) < 512:
            # disconnect(client) не отключаем, клиент сам отключится и произойдёт обработка в исключении
            if clients[client]['file_mode'] == OCTET_MODE:
                # Закрываем файл, так как все байты были получены
                closeFile(client)
            else:
                print("Error: Mode Not Found")
                return

        sendAck(client, blockNum)

# Функция для обработки ACK ответа
def ackResponse(client, packetEnd):
    (strBlockNum,) = struct.unpack("!H", packetEnd)
    blockNum = int(strBlockNum)
    if clients[client]['block_num'] == blockNum:
        if len(clients[client]['block_data']) < 512:

            # Надо сделать по таймауту
            disconnect(client)
            return
        blockNum += 1
        if clients[client]['file_mode'] == OCTET_MODE:
            sendData(client, blockNum)
        else:
            print("Error: Mode Not Found")
    else:
        print("Error. Unknown block")

def performOperation(client, packet):
    # https://stackoverflow.com/a/3753685
    (typeOp,), packetEnd = struct.unpack("!H", packet[:2]), packet[2:]
    print(packet)
    print(typeOp)

    if typeOp == RRQ:
        readRequest(client, packetEnd)
        return "RRQ"
    elif typeOp == WRQ:
        writeRequest(client, packetEnd)
        return "WRQ"
    elif typeOp == DATA:
        dataResponse(client, packetEnd)
        return "DATA"
    elif typeOp == ACK:
        ackResponse(client, packetEnd)
        return "ACK"
    elif typeOp == ERROR:
        print("5 type")
        return "ERROR"

    # Отправляем ошибку (неизвестный код операции)
    sendError(client, ERRORS["ITO"])
    return "???"

# Функция для работы с клиентом. Получаем сообщения и обрабатываем их
def handle(server):
    client = None
    try:
        while SERVER_WORKING:
            # Получаем пакет с информацией, что нужно хосту от сервера
            packet, client = server.recvfrom(HEADER)
            if client not in clients:
                clients[client] = {}
                print(f"Client - {client}")
                printLog(serverTime(), f"Connected with {str(client)}")

            textOp = performOperation(client, packet)

            printLog(serverTime(), f"[{client[0]}:{str(client[1])}] -> " + textOp)

    except ConnectionResetError:
        # Сработает также в случае, когда клиент загрузит на сервер файл и отключится (нет)
        if client != None:
            closeFile(client)
            disconnect(client)

# Функция для обработки подключения пользователей к серверу
def receive(server):
    global SERVER_WORKING
    try:
        while SERVER_WORKING:
            # sel.register(fileobj=client, events=selectors.EVENT_READ, data=handle)
            print()

    except KeyboardInterrupt:
        SERVER_WORKING = False
        print("---Server Stopped---")
        clients.clear()
        server.close()
        exit(0)

def startServer():
    sel.register(fileobj=server, events=selectors.EVENT_READ, data=handle)
    print("---Server Started---")

    while True:
        events = sel.select()
        for key, mask in events:
            callback = key.data
            callback(key.fileobj)

startServer()
