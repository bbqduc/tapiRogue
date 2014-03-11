import socket

class SystemMessage:
    def __init__(self, msg):
        self.msgtype = Message.SYSTEM_MESSAGE
        self.msg = msg
    def 

class Player:
    def __init__(self, playerid, name, socket):
        self.playerid = playerid
        self.name = name
        self.socket = socket

class Server:
    def __init__(self):
        self.players = {}
        self.nextid = 0

    def newConnection(self, socket, name):
        self.nextid += 1
        self.players[nextid] = Player(nextid, name, socket)
        self.broadCastMessage(SystemMessage(name + " connected."))

    def broadCastMessage(self, msg):
        for p in players:






TCP_IP = '127.0.0.1'
TCP_PORT = 5005
BUFFER_SIZE = 1024

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind((TCP_IP, TCP_PORT))
s.listen(1)

conn, addr = s.accept()
print 'connection address:', addr
while 1:
    data = conn.recv(BUFFER_SIZE)
    if not data: break
    print "received data ", data
    conn.send(data)

conn.close()
