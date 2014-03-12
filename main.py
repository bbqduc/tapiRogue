import libtcodpy as libtcod
import math
import socket
import time
import threading
import Queue
import msgpack
from io import BytesIO
import message as Message
from panels import TypingPanel, MessagePanel, StatusPanel
import errno
import tapirogueproperties as tapiRogueProperties
import areamap
from entity import Entity, CreateProperty


##### ugly globals

colors = { 'visible': {
        'wall': libtcod.Color(120, 110, 50),
        'ground': libtcod.Color(200, 180, 50)
    },
    'dark': {
        'wall': libtcod.Color(0, 0, 100),
        'ground': libtcod.Color(50, 50, 150)
        }
    }

COLOR_DARK_WALL = libtcod.Color(0, 0, 100)
COLOR_LIGHT_WALL = libtcod.Color(120, 110, 50)

COLOR_DARK_GROUND = libtcod.Color(50, 50, 150)
COLOR_LIGHT_GROUND = libtcod.Color(200, 180, 50)
TCP_RETRYCOUNT = 5


SCREEN_WIDTH = 150
SCREEN_HEIGHT = 60
LIMIT_FPS = 20


#######################################
class Effect:
    def __init__(self, lifetime):
       self.lifetime = lifetime
       self.timeactive = 0
    
    def tick(self, dt):
       self.timeactive += dt
    
    def destroy(self, console):
       pass

class SwordSwingEffect(Effect):
    def __init__(self, center):
       Effect.__init__(self, 0.5)
       self.center = center
       self.lastx = center.x
       self.lasty = center.y
       self.characters = [ '|', '/', '-', '\\', '|', '/', '-', '\\' ]
       self.diffs = [ (0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1) ]
    
    def display(self, console):
       self.clear(console)
       simindex = int(8*self.timeactive / self.lifetime)
       if simindex > 7:
          return
       x = self.center.x
       y = self.center.y
       libtcod.console_set_default_foreground(console, libtcod.red)
       (diffx, diffy) = self.diffs[simindex]
       c = self.characters[simindex]
       x += diffx
       y += diffy
       libtcod.console_put_char(console, x, y, c, libtcod.BKGND_NONE)
       self.lastx = x
       self.lasty = y
    
    def clear(self, console):
       libtcod.console_put_char(console, self.lastx, self.lasty, ' ', libtcod.BKGND_NONE)
    
    def destroy(self, console):
       self.clear(console)

class Game:
    def __init__(self):
        self.areamap = areamap.AreaMap(SCREEN_WIDTH, SCREEN_HEIGHT)
        self.serverconnection = ServerConnection(self)
        self.player = None
        self.createWindow()
        self.createPanels(SCREEN_WIDTH, SCREEN_HEIGHT)
        self.messageconsumer = MessageConsumer(self.serverconnection.incomingmessages, self.serverconnection.outgoingmessages, self)
        self.entities = {}
        self.lastmoveclock = time.clock()
        self.effects = []
    
    def createWindow(self):
        libtcod.console_set_custom_font('consolas10x10_gs_tc.png', libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_TCOD)
        libtcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, 'tapiRogue', False, libtcod.RENDERER_GLSL)
        libtcod.sys_set_fps(LIMIT_FPS)

    def createPanels(self, width, height):
        self.mainconsole = libtcod.console_new(SCREEN_WIDTH, SCREEN_HEIGHT)
        self.mainconsolewidth = SCREEN_WIDTH - 11
        self.mainconsoleheight = SCREEN_HEIGHT - 15
        self.msgpanel = MessagePanel(0, height-15, width/2, 10)
        self.combatlog = MessagePanel(width/2+1, height-15, width/2, 20)
        self.typingpanel = TypingPanel(width, height-2)

    def handle_keys(self):
        key = libtcod.console_check_for_keypress(True)

        if key.vk == libtcod.KEY_ENTER:
            if key.lalt:
                libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())
            elif self.typingpanel.active:
                self.serverconnection.putMessageOutQueue(Message.ChatMessage(self.player.name, self.typingpanel.message))
                self.typingpanel.message = ""
                self.typingpanel.active = False
                self.typingpanel.refreshMessage()
            else:
                self.typingpanel.active = True
                self.typingpanel.refreshMessage()
        elif key.vk == libtcod.KEY_ESCAPE:
            if self.typingpanel.active:
                self.typingpanel.active = False
            else:
                return True
        elif self.typingpanel.active:
            self.typingpanel.handleKey(key)
            return False
        elif key.vk == libtcod.KEY_SPACE:
           self.effects.append(SwordSwingEffect(self.player))
           return False

        xdir = 0
        ydir = 0
        
        if libtcod.console_is_key_pressed(libtcod.KEY_UP):
            ydir = -1
        elif libtcod.console_is_key_pressed(libtcod.KEY_DOWN):
            ydir = 1
        elif libtcod.console_is_key_pressed(libtcod.KEY_LEFT):
            xdir = -1
        elif libtcod.console_is_key_pressed(libtcod.KEY_RIGHT):
            xdir = 1

        if not (xdir == 0 and ydir == 0):
            t = time.clock()
            if t - self.lastmoveclock > 0.01:
                self.serverconnection.putMessageOutQueue(Message.MovementMessage(xdir, ydir))
                self.lastmoveclock = t

    def connect(self, ip, port):
        self.serverconnection.connect(ip, port)
        if not self.serverconnection.ok:
            print 'Failed to connect to server.'
            return
        state = self.serverconnection.requestFullStateAndPlayerCharacter()
        self.areamap.syncStaticsFromFullState(state)

        self.waitForFullState = True
        self.connectionthread = threading.Thread(target = self.serverconnection.run)
        self.connectionthread.start()

        print 'Static state synced.'

        while self.waitForFullState:
            time.sleep(0.01)
            self.messageconsumer.handleMessages()


        self.messageconsumer.handleMessages()
        self.statuspanel = StatusPanel(self.player, self.areamap.width-11, 3)
        self.run()

    def fullSync(state):
        self.areamap.syncStaticsFromFullState(state)
        self.syncEntitiesFromFullState(state)

    def syncEntitiesFromFullState(self, state):
#        print 'Got state :' + str(state)
        self.entities = {}
        for en in state['entities']:
            e = state['entities'][en]
            newe = Entity(e['x'], e['y'], e['char'], libtcod.Color(e['color_r'], e['color_g'], e['color_b']), e['name'], en)
            for p in e['properties']:
                newe.properties[p] = CreateProperty(p, e['properties'][p], self)
            self.entities[en] = newe

        self.player = self.entities[state['playerid']]
        self.areamap.recomputeLights(self.player)
        self.waitForFullState = False
    
    def syncEntitiesFromDiffState(self, diff):
        for i in diff:
           self.entities[i].x = diff[i]['x']
           self.entities[i].y = diff[i]['y']
        self.areamap.recomputeLights(self.player)

    def run(self):
        self.lastsimtime = time.clock()
        while not libtcod.console_is_window_closed():
            libtcod.console_set_default_foreground(self.mainconsole, libtcod.white)

            self.messageconsumer.handleMessages()

            t = time.clock()
            dt = t - self.lastsimtime
            self.lastsimtime = t
            neweffects = []
            for e in self.effects:
               e.clear(self.mainconsole)
               e.tick(dt)
               e.display(self.mainconsole)
               if e.timeactive < e.lifetime:
                  neweffects.append(e)
               else:
                  e.destroy(self.mainconsole)
            self.effects = neweffects

            self.render_all()
            libtcod.console_blit(self.mainconsole, 0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, 0, self.mainconsolewidth/2-self.player.x, self.mainconsoleheight/2-self.player.y)
            self.combatlog.display()
            self.msgpanel.display()
            self.statuspanel.display()
            self.typingpanel.display()
            libtcod.console_flush()

            for e in self.entities:
                self.entities[e].clear(self.mainconsole) # clear moving objects last position

            exit = self.handle_keys()
            if exit:
                break

            time.sleep(0.01)

#            for o in self.mapdata.entities: # todo : server logic
#                if o != self.player and 'basicai' in o.properties:
#                    o.properties['basicai'].takeTurn(mapdata, player) # TODO : timeout for monster
        self.serverconnection.stop = True
        self.connectionthread.join

        self.serverconnection.disconnect()


    def render_all(self):
        for e in self.entities:
            self.entities[e].draw(self.areamap.fovMap, self.mainconsole)
        for y in range(self.areamap.height):
            for x in range(self.areamap.width):
                key1 = 'dark'
                key2 = 'ground'
                if libtcod.map_is_in_fov(self.areamap.fovMap, x, y):
                    key1 = 'visible' 
                    self.areamap.tiles[x][y].explored = True

                if self.areamap.tiles[x][y].block_sight: 
                    key2 = 'wall'

                if self.areamap.tiles[x][y].explored:
                    libtcod.console_set_char_background(self.mainconsole, x, y, colors[key1][key2], libtcod.BKGND_SET)
        self.player.draw(self.areamap.fovMap, self.mainconsole)


    def show_status(self, con):
        libtcod.console_set_default_foreground(con, libtcod.white)
        hptext = "Dead."
        if self.player.properties['combat'] is not None:
            hptext = 'HP: ' + str(self.player.properties['combat'].hp) + '/' + str(self.player.properties['combat'].max_hp)
        libtcod.console_print_ex(con, 1, 0, libtcod.BKGND_NONE, libtcod.LEFT,
                hptext)

    def displayKillMessage(self, killed, killer):
        self.combatlog.appendMessage(killer.capitalize() + " killed " + killed + "!")

    def player_death(self, player, killer):
        self.displayKillMessage(player.name, killer.name)
        print 'You died!'
        player.char = '%'
        player.color = libtcod.dark_red
        player.properties['combat'] = None

    def monster_death(self, monster, killer):
        self.displayKillMessage(monster.name, killer.name)
        print monster.name.capitalize() + ' is dead!'
        monster.char = '%'
        monster.blocks = False
        monster.properties['combat'] = None
        monster.properties['ai'] = None
        monster.name = 'remains of ' + monster.name
        # TODO : monster send to back

class ServerConnection:
    def __init__(self, game):
        self.tcpsocket = None
        self.incomingmessages = Queue.Queue()
        self.outgoingmessages = Queue.Queue()
        self.incomingbuffer = BytesIO()
        self.outgoingbuffer = BytesIO()
        self.ok = False
        self.unpacker = msgpack.Unpacker()
        self.packer = msgpack.Packer()
        self.game = game

    def connect(self, ip, port):
        self.serverip = ip
        self.serverport = port
        if self.tcpsocket is not None:
            self.tcpsocket.close()
        self.ok = False
        self.tcpsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcpsocket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.tcpsocket.settimeout(5)

        for i in range(TCP_RETRYCOUNT):
            try:
                print('Connecting to ' + ip + ":" + str(port) + "...")
                self.tcpsocket.connect((ip, port))
                print('Connected.')
                self.ok = True
                break
            except socket.timeout:
                print('Timed out. Retrying..')
                pass
            except socket.error as (errno, msg):
                print('ERROR : ' + msg)
                break
        self.tcpsocket.settimeout(0)

    def requestFullStateAndPlayerCharacter(self):
        self.tcpsocket.setblocking(True)
        msg = self.packer.pack(Message.ConnectMessage())

        staticstate = False

        while staticstate == False:
            self.unpacker.feed(self.tcpsocket.recv(1024))
            for o in self.unpacker:
                staticstate = o['state']
                break
        self.tcpsocket.setblocking(False)
        return staticstate

    def disconnect(self):
        self.putMessageOutQueue(Message.DisconnectMessage())
        try:
            self.sendMessages()
        except:
            pass

    def putMessageOutQueue(self, msg):
        try:
            self.outgoingmessages.put(msg)
        except Queue.Full:
            msgpanel.appendClientMessage("INCOMING MESSAGE QUEUE FULL, MUCHOS PROBLEM!!!!!")

    def putMessageInQueue(self, msg):
        try:
            self.incomingmessages.put(msg)
        except Queue.Full:
            msgpanel.appendClientMessage("INCOMING MESSAGE QUEUE FULL, MUCHOS PROBLEM!!!!!")
    
    def parsemessages(self):
        for unpacked in self.unpacker:
            self.putMessageInQueue(unpacked)

    def sendMessages(self):
        ## send outgoing messages
        try:
            msg = self.outgoingmessages.get(False)
            self.tcpsocket.send(self.packer.pack(msg))
        except Queue.Empty:
            pass

    def receiveMessages(self):
        ## check for incoming messages
        try:
            msg = self.tcpsocket.recv(1024)
            self.unpacker.feed(msg)
            self.parsemessages()
        except socket.error as (errorcode, msg):
            if errorcode != errno.EWOULDBLOCK:
                self.game.msgpanel.appendClientMessage("Connection error: " + msg)

    def run(self):
        self.stop = False
        while not self.stop:
            self.receiveMessages()
            self.sendMessages()
            time.sleep(0.01)

class MessageConsumer:
    def __init__(self, incomingmessages, outgoingmessages, game):
        self.inmessages = incomingmessages
        self.outmessages = outgoingmessages
        self.game = game

    def handleMessages(self):
        while 1:
            try:
                msg = self.inmessages.get(False)
                self.handleMessage(msg)
            except Queue.Empty:
                break

    def handleMessage(self, msg):
#        print 'Received message: ' + str(msg)
        msgtype = msg['type']
        if msgtype == Message.CHAT_MESSAGE:
            self.game.msgpanel.appendMessage(msg['sender'] + "> " + msg['msg'])
        elif msgtype == Message.SYSTEM_MESSAGE:
            self.game.msgpanel.appendServerMessage(msg['msg'])
        elif msgtype == Message.PONG:
            self.game.ping = msg.ping # TODO
        elif msgtype == Message.FULL_STATE_MESSAGE:
            self.game.syncEntitiesFromFullState(msg['state'])
        elif msgtype == Message.DIFF_STATE_MESSAGE:
            self.game.syncEntitiesFromDiffState(msg['state'])
        else:
            print('Message of unknown type ' + str(msgtype) + ' received.')

game = Game()
game.connect('127.0.0.1', 5005)
#game.connect('bduc.org', 5005)
#libtcod.console_set_custom_font('arial.ttf', libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_TCOD)


#player = Entity(15, 13, '@', libtcod.white, 'player', True)
#player.AddProperty('combat', {'hp': 20, 'defense':2, 'power':5, 'deathfunction':'player_death'}, globals())
