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
PORT = 4000  # порт

RRQ = 1
WRQ = 2
DATA = 3
ACK = 4
ERROR = 5

OCTET_MODE = 'octet'

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((HOST, PORT))

server.listen(5)
server.setblocking(False)
sel = selectors.DefaultSelector()

clients = {}  # адреса и данные (!) подключенных клиентов

def serverTime():
    return datetime.timestamp(datetime.now())

def serverTimeFormat(mytime):
    return datetime.strftime(datetime.fromtimestamp(mytime  + time.timezone), "%Y-%m-%d-%H.%M.%S")

def printLog(time, message):
    print(f"[{serverTimeFormat(time)}]/[log]: {message}")

# Функция для отправки сообщения подключенным пользователям
def broadcast(muteClient, data):
    for client in clients.keys():
        if client != muteClient:
            client.send(data)

# Функция для отключения клиента от сервера
def disconnect(client):
    addres = client.getsockname()
    sel.unregister(client)
    clients.pop(client)
    client.close()
    leftmsg = f"[{addres[0]}:{str(addres[1])}] -> DISCONNECT"
    printLog(serverTime(), leftmsg)

# Функция для отправки блока данных клиенту
def sendData(client, oldFileData, blockNum):
    blockData = oldFileData[:512]
    fileData = oldFileData[512:]
    packet = struct.pack(f"!HH{len(blockData)}s", DATA, blockNum, blockData)

    clients[client]['block_num'] = blockNum
    clients[client]['block_data'] = blockData
    clients[client]['file_data'] = fileData

    client.send(packet)

# Функция для отправки ACK клиенту
def sendAck(client, blockNum):
    packet = struct.pack(f"!HH", ACK, blockNum)
    clients[client]['block_num'] = blockNum
    client.send(packet)

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
            f = open(fileName, 'rb')
            fileData = f.read()
            f.close()
            print(fileData)

            blockNum = 1
            sendData(client, fileData, blockNum)
        else:
            print("Error: Mode Not Found")
    except FileNotFoundError as e:
        print("Error: FileNotFoundError")
        # ТУТ ОТПРАВЛЯТЬ ОШИБКУ КЛИЕНТУ
        print(e)

# Функция для обработки WRQ запроса
def writeRequest(client, packetEnd):
    fileAndMode = packetEnd.split(b'\x00')
    fileName = fileAndMode[0].decode("ascii")
    mode = fileAndMode[1].decode("ascii")
    print(fileName)
    print(mode)

    try:
        if os.path.exists(fileName):
            print("Error. File Is Exists")
            # ТУТ ОТПРАВЛЯТЬ ОШИБКУ КЛИЕНТУ
        else:
            blockNum = 0
            clients[client]['file_name'] = fileName
            clients[client]['file_mode'] = mode
            if mode == OCTET_MODE:
                clients[client]['file_data'] = b''
            else:
                print("Error: Mode Not Found")
            sendAck(client, blockNum)
    except ValueError:
        print("Error path")
        # ТУТ ОТПРАВЛЯТЬ ОШИБКУ КЛИЕНТУ

# Функция для обработки DATA ответа
def dataResponse(client, packetEnd):
    (strBlockNum,), blockData = struct.unpack("!H", packetEnd[:2]), packetEnd[2:]
    blockNum = int(strBlockNum)
    oldBlockNum = clients[client]['block_num']
    # Пришёл повторный кусок данных, а значит клиент не получил наш ACK
    if oldBlockNum == blockNum:
        sendAck(client, blockNum)
    elif oldBlockNum + 1 == blockNum:
        clients[client]['file_data'] += blockData

        if len(blockData) < 512:
            # disconnect(client) не отключаем, клиент сам отключится и произойдёт обработка в исключении
            if clients[client]['file_mode'] == OCTET_MODE:
                f = open(clients[client]['file_name'], 'xb')
                f.write(clients[client]['file_data'])
                f.close()
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
            disconnect(client)
            return
        blockNum += 1
        if clients[client]['file_mode'] == OCTET_MODE:
            fileData = clients[client]['file_data']
            sendData(client, fileData, blockNum)
        else:
            print("Error: Mode Not Found")
    else:
        print("Error. Unknown block")

# Функция для работы с клиентом. Получаем сообщения и обрабатываем их
def handle(client):
    try:
        if SERVER_WORKING:
            # Получаем пакет с информацией, что нужно хосту от сервера
            packet = client.recv(HEADER)
            # https://stackoverflow.com/a/3753685
            (typeOp,), packetEnd = struct.unpack("!H", packet[:2]), packet[2:]
            print(packet)
            print(typeOp)

            textOp = "???"
            if typeOp == RRQ:
                readRequest(client, packetEnd)
                textOp = "RRQ"
            elif typeOp == WRQ:
                writeRequest(client, packetEnd)
                textOp = "WRQ"
            elif typeOp == DATA:
                dataResponse(client, packetEnd)
                textOp = "DATA"
            elif typeOp == ACK:
                ackResponse(client, packetEnd)
                textOp = "ACK"
            elif typeOp == ERROR:
                print("5 type")
                textOp = "ERROR"

            addres = client.getsockname()
            printLog(serverTime(), f"[{addres[0]}:{str(addres[1])}] -> " + textOp)

    except ConnectionResetError:
        # Сработает также в случае, когда клиент загрузит на сервер файл и отключится
        disconnect(client)

# Функция для обработки подключения пользователей к серверу
def receive(server):
    global SERVER_WORKING
    try:
        if SERVER_WORKING:
            client, addres = server.accept()
            clients[client] = {}
            printLog(serverTime(), f"Connected with {str(addres)}")
            client.setblocking(False)
            sel.register(fileobj=client, events=selectors.EVENT_READ, data=handle)
    except KeyboardInterrupt:
        SERVER_WORKING = False
        print("---Server Stopped---")
        for client in clients.keys():
            sel.unregister(client)
            client.close()
        clients.clear()
        server.close()
        exit(0)

def startServer():
    # Src: https://docs.python.org/3/library/selectors.html#examples
    sel.register(fileobj=server, events=selectors.EVENT_READ, data=receive)
    print("---Server Started---")

    while True:
        events = sel.select()
        for key, mask in events:
            callback = key.data
            callback(key.fileobj)

startServer()
