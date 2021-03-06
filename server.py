import socket
import msgpack
import Queue
import threading
import signal, os
import time
import message as Message
import errno
import areamap
import libtcodpy as libtcod
from entity import Entity, CreateProperty
import util

class PlayerInput:
   INPUT_EMPTY = 0
   INPUT_MOVE = 1
   INPUT_MELEE = 2
   @staticmethod
   def Move(xdir, ydir):
      return {'type': PlayerInput.INPUT_MOVE, 'xdir': xdir, 'ydir': ydir}
   @staticmethod
   def Melee(direction):
      return {'type': PlayerInput.INPUT_MELEE, 'dir': direction}
   @staticmethod
   def Empty():
      return {'type': PlayerInput.INPUT_EMPTY }


mapdata =  {
            'rooms': [ {'x1': 10, 'y1':10, 'width':10, 'height':20},
                {'x1': 50, 'y1':10, 'width':10, 'height':20}
                ],
            'vtunnels': [],
            'htunnels': [{'x1': 16, 'x2': 52, 'y': 15, 'width': 3}]
            }

ACTIONCOOLDOWN = 0.01

class Player:
    def __init__(self, playerid, entityid, name, socket, server):
        self.server = server
        self.playerid = playerid
        self.entityid = entityid 
        self.entity = self.server.entities[entityid]
        self.name = name
        self.socket = socket
        self.outmessages = Queue.Queue()
        self.inmessages = Queue.Queue()
        self.packer = msgpack.Packer()
        self.unpacker = msgpack.Unpacker()
        self.lastTickSent = -1
        self.nextInput = PlayerInput.Empty()
        self.actionCooldown = 0
    
    def tick(self, dt):
       if self.actionCooldown > 0:
          self.actionCooldown -= dt
       if self.nextInput['type'] != PlayerInput.INPUT_EMPTY:
          if self.actionCooldown <= 0:
             if self.nextInput['type'] == PlayerInput.INPUT_MOVE:
                self.entity.move(self.server.areamap, self.nextInput['xdir'], self.nextInput['ydir'])
             elif self.nextInput['type'] == PlayerInput.INPUT_MELEE:
                self.server.diffpacket[self.entityid] = { 'event': 'melee' } # todo : enum or something

             self.actionCooldown = ACTIONCOOLDOWN
             self.server.changed = True
          self.nextInput = PlayerInput.Empty()


    def sendMessages(self):
        while 1:
            try:
                msg = self.outmessages.get(False)
                packed = self.packer.pack(msg)
                self.socket.send(packed)
            except Queue.Empty:
                break
            except socket.error as (errorcode, msg):
                if errorcode != errno.EWOULDBLOCK:
                    raise
        if self.lastTickSent != self.server.tick:
            msg = self.server.diffpacket
            if self.lastTickSent == -1:
               print 'Sending full state!'
               msg = self.server.fullstatepacket
               msg['state']['playerid'] = self.entityid
            self.lastTickSent = self.server.tick
            packed = self.packer.pack(msg)
            self.socket.send(packed)

    def checkSocket(self): # todo : naming
        try:
            self.unpacker.feed(self.socket.recv(8)) # need to check the ret?
            self.parsemessages()
        except socket.error as (errorcode, msg):
            if errorcode != errno.EWOULDBLOCK:
                raise

    def parsemessages(self):
        for unpacked in self.unpacker:
            self.server.packethandler.enQueueMessage(unpacked, self.playerid)

class PacketHandler:
    def __init__(self, players, server):
        self.ip = '127.0.0.1'
#        self.ip = 'bduc.org'
        self.port = 5006
        self.players = players
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.socket.bind((self.ip, self.port))
        self.socket.listen(1)
        self.socket.setblocking(False)
        self.server = server
        self.stop = False
        print ('Started listening on port ' + str(self.port))

    def enQueueMessage(self, msg, senderid):
        if msg['type'] == Message.CLIENT_DISCONNECT:
            msg['id'] = senderid

        try:
            self.server.inmessages.put((msg,senderid))
        except Queue.Full:
            print("INCOMING MESSAGE QUEUE FULL, MUCHOS PROBLEM!!!!!") # we are fuckad, simply

    def run(self):
        self.stop = False

        while not self.stop:
            # process existing players
            for p in self.players:
                try:
                    self.players[p].checkSocket()
                except socket.error:
                    msg = Message.DisconnectMessage()
                    msg['id'] = p
                    self.enQueueMessage(msg, p)

            # check for new players
            try:
                (conn, address) = self.socket.accept()
                conn.setblocking(False)
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                self.enQueueMessage({'type': Message.NEW_CLIENT_CONNECTION, 'name': 'Jorma', 'socket': conn}, None)
            except socket.error:
                pass

            time.sleep(0.01)

class Server:
    def __init__(self):
        self.diffpacket = {}
        self.players = {}
        self.nextid = 0
        self.nextentityid = 0
        self.inmessages = Queue.Queue()
        self.outmessages = Queue.Queue()
        self.packethandler = PacketHandler(self.players, self)
        self.packethandlerthread = threading.Thread(target = self.packethandler.run)
        self.entities = {}
        self.areamap = areamap.AreaMap(150, 60)
        self.areamap.syncStaticsFromFullState(mapdata)
        self.tick = 0
        self.makeStatePacket()
        self.makeStaticStatePacket()

    def makeStaticStatePacket(self):
        self.staticstatepacket = Message.FullStaticStateMessage(self.areamap.serialize())

    def makeStatePacket(self): # todo : dont need to make full state packet if no one has requested it
        state = { 'entities': {} }
        for e in self.entities:
            state['entities'][e] = self.entities[e].serialize()
        self.fullstatepacket = Message.FullStateMessage(state)
        self.tick += 1

    def newConnection(self, socket, name):
        self.nextid += 1
        self.nextentityid += 1
        e = Entity(15, 13, '@', libtcod.white, name, self.nextentityid, True)
        e.AddProperty('combat', {'hp': 20, 'max_hp':20, 'defense':2, 'power':5, 'deathfunction':None}, None)
        e.server = self
        self.entities[self.nextentityid] = e
        player = Player(self.nextid, self.nextentityid, name, socket, self)
        self.enQueueMessage(player, self.staticstatepacket)
        self.players[self.nextid] = player
        self.broadCastMessage(Message.SystemMessage(name + " connected."))
        self.diffpacket[self.nextentityid] = e.serialize()
        e.tick = player.tick

        self.nextentityid += 1
        enemy = Entity(55, 13, 'o', libtcod.magenta, 'orc', self.nextentityid,True)
        enemy.AddProperty('combat', {'hp': 20, 'max_hp':20, 'defense':2, 'power':5, 'deathfunction':None}, None)
        enemy.AddProperty('basicai', {}, None)
        enemy.server = self
        enemy.properties['basicai'].owner = enemy
        enemy.properties['basicai'].activate(e)
        enemy.tick = enemy.properties['basicai'].tick
        self.entities[self.nextentityid] = enemy

        self.diffpacket[self.nextentityid] = enemy.serialize() # todo : dont need to serialize ai !!
        self.makeStatePacket()

        print (name + ' connected.')

    def broadCastMessage(self, msg):
        for p in self.players:
            self.enQueueMessage(self.players[p], msg)

    def enQueueMessage(self, player, msg):
        try:
            player.outmessages.put(msg)
        except Queue.Full:
            print("OUTGOING MESSAGE QUEUE FULL, MUCHOS PROBLEM!!!!!")

    def start(self):
        self.packethandlerthread.start()
        self.run()

    def disconnectClient(self, playerid):
        try:
            p = self.players[playerid]
            del self.players[playerid]
            del self.entities[p.entityid]
            p.socket.shutdown(socket.SHUT_RDWR)
            p.socket.close()
            print (p.name + ' disconnected.')
            self.broadCastMessage({'type': Message.CLIENT_DISCONNECT, 'id': p.entityid})
        except KeyError:
            pass # todo: how is it possible ???

    def handleMessage(self, msg, playerid):
#        print 'Received message: ' + str(msg)
        if msg['type'] == Message.NEW_CLIENT_CONNECTION:
            self.newConnection(msg['socket'], msg['name'])
        elif msg['type'] == Message.CLIENT_DISCONNECT:
            self.disconnectClient(msg['id'])
        elif msg['type'] == Message.CLIENT_CONNECT:
            self.newConnection(msg['socket'], msg['name'])
        elif msg['type'] == Message.CHAT_MESSAGE:
            self.broadCastMessage(msg)
        elif msg['type'] == Message.MOVEMENT_MESSAGE:
            self.players[playerid].nextInput = PlayerInput.Move(msg['xdir'], msg['ydir'])
        elif msg['type'] == Message.ACTION_MESSAGE:
            self.players[playerid].nextInput = PlayerInput.Melee(None) # todo : add direction
        else:
            print 'Unhandled message type : ' + str(msg['type'])

    def run(self):
        self.changed = False
        self.lastsimtime = util.clock()
        while not self.packethandler.stop:
            # handle server events
            self.diffpacket = {}
            while 1:
                try:
                    (msg, sender) = self.inmessages.get(False)
#                    print 'Handling message ' + str(msg)
                    self.handleMessage(msg, sender)
                except Queue.Empty:
                    break

            t = util.clock()
            dt = t - self.lastsimtime
            self.lastsimtime = t
            # handle individual player events
            for e in self.entities:
                self.entities[e].tick(dt)
#            for p in self.players:
#                self.players[p].tick(dt)

            if self.changed:
               self.makeStatePacket()
               self.changed = False

            self.diffpacket = Message.DiffStateMessage(self.diffpacket)
            for p in self.players:
                try:
                    self.players[p].sendMessages()
                except socket.error:
                    self.disconnectClient(p)

#            time.sleep(0.03)

    def stop(self, signum, frame):
        self.packethandler.stop = True
        self.packethandlerthread.join()

server = Server ()

signal.signal(signal.SIGINT, server.stop)
server.start()
