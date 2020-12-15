import os
import socket
import struct
import threading
import time
from datetime import datetime

HEADER = 600
CLIENT_WORKING = True
CONNECT_WORKING = True
SERVER_IP = "127.0.0.1"
# SERVER_IP = "51.15.130.137"
SERVER_PORT = 4000

RRQ = 1
WRQ = 2
DATA = 3
ACK = 4
ERROR = 5

OCTET_MODE = 'octet'

data = {}  # данные (!) для работы с сервером

def clientTime():
    return datetime.timestamp(datetime.now())

def getData(time, nickname, message):
    data = f"{time}\0{nickname}\0{message}".encode("ascii")
    return f"{len(data):<{HEADER}}".encode("ascii") + data

def parseCommand(command):
    commandList = command.split(" ")
    try:
        if commandList[0] == 'put':
            if os.path.exists(commandList[2]):
                commandList[0] = WRQ
                return commandList
            else:
                print("Current local file is not found")
        elif commandList[0] == 'get':
            if os.path.exists(commandList[2]):
                print("Current local file is exists")
            else:
                commandList[0] = RRQ
                return commandList
    except ValueError:
        print("Error path")
    return None

# Функция для отправки блока данных клиенту
def sendData(client, oldFileData, blockNum):
    blockData = oldFileData[:512]
    fileData = oldFileData[512:]
    packet = struct.pack(f"!HH{len(blockData)}s", DATA, blockNum, blockData)

    data['block_num'] = blockNum
    data['block_data'] = blockData
    data['file_data'] = fileData

    client.send(packet)

# Функция для отправки ACK клиенту
def sendAck(client, blockNum):
    packet = struct.pack(f"!HH", ACK, blockNum)
    data['block_num'] = blockNum
    client.send(packet)

# Функция для обработки DATA ответа
def dataResponse(client, packetEnd):
    (strBlockNum,), blockData = struct.unpack("!H", packetEnd[:2]), packetEnd[2:]
    blockNum = int(strBlockNum)
    oldBlockNum = data['block_num']
    # Пришёл повторный кусок данных, а значит клиент не получил наш ACK
    if oldBlockNum == blockNum:
        sendAck(client, blockNum)
    elif oldBlockNum + 1 == blockNum:
        data['file_data'] += blockData

        if len(blockData) < 512:
            # disconnect(client) не отключаем, клиент сам отключится и произойдёт обработка в исключении
            if data['file_mode'] == OCTET_MODE:
                f = open(data['file_name'], 'xb')
                f.write(data['file_data'])
                f.close()
            else:
                print("Error: Mode Not Found")
            return

        sendAck(client, blockNum)

# Функция для обработки ACK ответа
def ackResponse(client, packetEnd):
    global CONNECT_WORKING
    (strBlockNum,) = struct.unpack("!H", packetEnd)
    blockNum = int(strBlockNum)
    if data['block_num'] == blockNum:
        if blockNum != 0 and len(data['block_data']) < 512:
            client.close()
            CONNECT_WORKING = False
            return
        blockNum += 1
        if data['file_mode'] == OCTET_MODE:
            fileData = data['file_data']
            sendData(client, fileData, blockNum)
        else:
            print("Error: Mode Not Found")
    else:
        print("Error. Unknown block")


# Функция для обработки информации, приходящей с сервера
def receive(client):
    global CONNECT_WORKING, CLIENT_WORKING
    try:
        while CONNECT_WORKING:
            # Получаем пакет с информацией, что нужно хосту от сервера
            packet = client.recv(HEADER)
            # https://stackoverflow.com/a/3753685
            (typeOp,), packetEnd = struct.unpack("!H", packet[:2]), packet[2:]
            print(typeOp)

            textOp = "???"
            if typeOp == DATA:
                dataResponse(client, packetEnd)
                textOp = "DATA"
            elif typeOp == ACK:
                ackResponse(client, packetEnd)
                textOp = "ACK"
            elif typeOp == ERROR:
                print("5 type")
                textOp = "ERROR"

            print(f"Server -> " + textOp)

    except ConnectionResetError:
        CONNECT_WORKING = False
        print("Error")
        client.close()
        return
    except KeyboardInterrupt:
        CLIENT_WORKING = False
        CONNECT_WORKING = False
        print("Client Exit")
        client.close()
        exit(0)

def clientStart():
    global CONNECT_WORKING, CLIENT_WORKING
    client = None
    try:
        while CLIENT_WORKING:
            commandList = None
            while commandList == None:
                # put серверный_файл локальный_файл
                # get серверный_файл локальный_файл
                command = input("Enter command: ")
                commandList = parseCommand(command)

            typeOp = commandList[0]
            fileName = commandList[1]
            mode = OCTET_MODE
            packet = struct.pack(f"!H{len(fileName)}sx{len(mode)}sx", typeOp, bytes(fileName, "ascii"),
                                 bytes(mode, "ascii"))
            data['file_name'] = commandList[2]
            data['file_mode'] = mode
            data['block_num'] = 0
            if mode == OCTET_MODE:
                if typeOp == RRQ:
                    data['file_data'] = b''
                elif typeOp == WRQ:
                    f = open(data['file_name'], 'rb')
                    fileData = f.read()
                    f.close()
                    print(fileData)
                    data['file_data'] = fileData
            else:
                print("Error: Mode Not Found")

            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                client.connect((SERVER_IP, SERVER_PORT))
                client.send(packet)
                CONNECT_WORKING = True
                receive(client)
            except ConnectionRefusedError:
                print(f"Server ({SERVER_IP}:{SERVER_PORT}) is not available")

            client = None

    except KeyboardInterrupt:
        CLIENT_WORKING = False
        CONNECT_WORKING = False
        print("Client Exit")
        if client != None:
            client.close()
        exit(0)

# Для обеспечения правильного поведения консоли (при закрытии)
def on_exit(sig, func=None):
    print("exit handler")
    time.sleep(10)  # so you can see the message before program exits

clientThread = threading.Thread(target=clientStart)
clientThread.start()
