COMMAND = ["list", "result", "get", "disconnect"]


class Types_Server:
    LIST = "0"
    NEXT_QRT = "1"
    RESULT = "2"
    DISCONNECT = "3",
    ERR = "4"


class Types_Client:
    REG = "0"
    AUTH = "1"
    LIST = "2"
    RESULT = "3"
    TEST = "4"
    ANSWER = "5"
    DISCONNECT = "6"
