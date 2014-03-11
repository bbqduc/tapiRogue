import libtcodpy as libtcod
import math
import socket
import time
import threading
import queue
from io import BytesIO

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

MAX_ROOM_MONSTERS = 3

FOV_ALGO = 0
FOV_LIGHT_WALLS = True
TORCH_RADIUS = 10

SCREEN_WIDTH = 150
SCREEN_HEIGHT = 60
LIMIT_FPS = 20

class TypingPanel:
    def __init__(self):
        self.message = ""
        self.x = 1
        self.y = SCREEN_HEIGHT-2
        self.width = SCREEN_WIDTH
        self.height = 1
        self.console = libtcod.console_new(self.width, self.height)
        self.active = False

    def handleKey(self, key):
        if key.vk == libtcod.KEY_BACKSPACE and len(self.message) > 0:
            self.message = self.message[:-1]
            self.refreshMessage()
        elif key.vk == libtcod.KEY_CHAR or key.c != 0:
            self.message += chr(key.c)
            self.refreshMessage()


    def refreshMessage(self):
        libtcod.console_set_default_foreground(self.console, libtcod.white)
        libtcod.console_print_ex(self.console, 1, 0, libtcod.BKGND_NONE, libtcod.LEFT, ('{0: <' + str(self.width) + '}').format(self.message))
        if self.active:
            libtcod.console_put_char(self.console, 1+len(self.message), 0, '_', libtcod.BKGND_NONE)
        else:
            libtcod.console_put_char(self.console, 1+len(self.message), 0, ' ', libtcod.BKGND_NONE)

    def display(self):
        libtcod.console_blit(self.console, 0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, 0, self.x, self.y)

class StatusPanel:
    def __init__(self, player):
        self.player = player
        self.x = SCREEN_WIDTH-11
        self.y = 3
        self.width = 10
        self.height = 10
        self.console = libtcod.console_new(self.width, self.height)

    def display(self):
        libtcod.console_set_default_foreground(self.console, libtcod.white)
        hptext = "Dead."
        if self.player.properties['combat'] is not None:
            hptext = 'HP: ' + str(self.player.properties['combat'].hp) + '/' + str(self.player.properties['combat'].max_hp)
        libtcod.console_print_ex(self.console, 1, 0, libtcod.BKGND_NONE, libtcod.LEFT, ('{0: <' + str(self.width) + '}').format(hptext))
        libtcod.console_blit(self.console, 0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, 0, self.x, self.y)

class MessagePanel:
    def __init__(self, x, y, width, height):
        self.x = x
        self.y = y
        self.console = libtcod.console_new(width, height)
        self.lines = []
        self.width = width
        self.height = height

    def repaintMessages(self):
        j=0
        for i in self.lines:
            libtcod.console_print_ex(self.console, 1, j, libtcod.BKGND_NONE, libtcod.LEFT, ('{0: <' + str(self.width) + '}').format(i))
            j += 1

    def appendMessage(self, msg): # TODO : compact repeating messages with (x16) etc, necessary?
        libtcod.console_set_default_foreground(self.console, libtcod.white)
        leftovermessage = ""
        if len(msg) >= self.width:
            leftovermessage = msg[self.width-1:]

        if len(self.lines) >= self.height:
            self.lines = self.lines[1:]
        self.lines.append(msg)
        if leftovermessage != "":
            self.appendMessage(leftovermessage)
        else:
            self.repaintMessages()

    def appendClientMessage(self, msg):
        self.appendMessage("[CLIENT] " + msg)
    def appendServerMessage(self, msg):
        self.appendMessage("[SERVER] " + msg)

    def display(self):
        libtcod.console_blit(self.console, 0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, 0, self.x, self.y)
        

class CombatObject:
    def __init__(self, hp, defense, power, deathfunction = None):
        self.max_hp = hp
        self.hp = hp
        self.defense = defense
        self.power = power
        self.deathfunction = deathfunction

    def hit(self, target):
        global combatlog
        if 'combat' not in target.properties or target.properties['combat'] is None:
            return
        damagedealt = target.properties['combat'].takeDamage(self.power, self)

    def takeDamage(self, damage, attacker):
        if damage >= 0:
            combatlog.appendMessage(attacker.owner.name.capitalize() + ' attacks ' + self.owner.name + ' for ' + str(damage) + " damage.")
        else:
            combatlog.appendMessage(attacker.owner.name.capitalize() + ' heals ' + self.owner.name + ' for ' + str(damage) + " hitpoints.")
        self.hp -= damage
        if self.hp <= 0:
            function = self.deathfunction
            if function is not None:
                function(self.owner, attacker.owner)
        return damage

class BasicMonster:
    def takeTurn(self, areamap, player):
        if libtcod.map_is_in_fov(areamap.fovMap, self.owner.x, self.owner.y):
            if self.owner.distanceTo(player.x, player.y) >= 2:
                self.moveTowards(player.x, player.y, areamap)
            else:
                self.owner.properties['combat'].hit(player)

    def moveTowards(self, target_x, target_y, areamap):
        dx = target_x - self.owner.x
        dy = target_y - self.owner.y
        distance = self.owner.distanceTo(target_x, target_y)
        dx = int(round(dx / distance))
        dy = int(round(dy / distance))

        self.owner.move(areamap, dx,dy)

class Rect:
    def __init__(self, x, y, w, h):
        self.x1 = x
        self.x2 = x+w
        self.y1 = y
        self.y2 = y+h


class Room:
    def __init__(self, tiles, rect):
        self.rect = rect
        for x in range(rect.x1+1, rect.x2):
            for y in range(rect.y1+1, rect.y2):
                tiles[x][y].blocked = False
                tiles[x][y].block_sight = False
        self.rect.x1 += 1
        self.rect.x2 -= 1
        self.rect.y1 += 1
        self.rect.y2 -= 1

class Tile:
    def __init__(self, blocked, block_sight=None):
        self.blocked = blocked
        self.explored = False

        if block_sight is None: block_sight=blocked
        self.block_sight = block_sight

class AreaMap:
    def __init__(self, width, height):
        self.width = width
        self.height = height

        self.tiles = [[ Tile(True)
            for y in range(height) ]
            for x in range(width) ]

        self.rooms = []
        self.makeRoom(Rect(20, 15, 10, 15))
        self.makeRoom(Rect(50, 15, 10, 15))

        self.makeHorizontalTunnel(25, 55, 23)

        self.fovMap = libtcod.map_new(width, height)
        for y in range(height):
            for x in range(width):
                libtcod.map_set_properties(self.fovMap, x, y, not self.tiles[x][y].block_sight, not self.tiles[x][y].blocked)

        self.entities = []

    def makeRoom(self, rect):
        self.rooms.append(Room(self.tiles, rect))

    def makeHorizontalTunnel(self, x1, x2, yc, width=5):
        top = yc-width/2
        for x in range(x1, x2+1):
            for y in range(top, yc+width):
                self.tiles[x][y].blocked = False
                self.tiles[x][y].block_sight = False

    def makeVerticalTunnel(self, y1, y2, xc, width=5):
        left = xc-width/2
        for x in range(left, xc+width):
            for y in range(y1, y2+1):
                self.tiles[x][y].blocked = False
                self.tiles[x][y].block_sight = False

    def recomputeLights(self, player):
        libtcod.map_compute_fov(self.fovMap, player.x, player.y, TORCH_RADIUS, FOV_LIGHT_WALLS, FOV_ALGO)

    def isBlocked(self, x, y):
        if self.tiles[x][y].blocked:
            return True

        for entity in self.entities:
            if entity.x == x and entity.y == y and entity.blocks:
                return True

        return False

        
class Entity:
    def __init__(self, x, y, char, color, name, blocks=True, properties={}):
        self.x = x
        self.y = y
        self.char = char
        self.color = color
        self.name = name
        self.blocks = blocks
        self.properties = properties
        for p in self.properties:
            self.properties[p].owner = self
#        self.lightsource = False

    def draw(self, fov):
        if libtcod.map_is_in_fov(fov, self.x, self.y):
            libtcod.console_set_default_foreground(con, self.color)
            libtcod.console_put_char(con, self.x, self.y, self.char, libtcod.BKGND_NONE)

    def clear(self):
        libtcod.console_put_char(con, self.x, self.y, ' ', libtcod.BKGND_NONE)

    def move(self, areamap, xdir, ydir):
        if not areamap.isBlocked(self.x+xdir, self.y+ydir):
            self.x += xdir
            self.y += ydir
#            if self.lightsource:
#                areamap.recomputeLights(self)
    def distanceTo(self, x, y):
        dx = x - self.x
        dy = y - self.y
        return math.sqrt(dx ** 2 + dy ** 2)
        

def handle_keys(player, areamap, typingpanel):
    key = libtcod.console_check_for_keypress(True)

    if key.vk == libtcod.KEY_ENTER:
        if key.lalt:
            libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())
        elif typingpanel.active:
            msgpanel.appendMessage(player.name + "> " + typingpanel.message)
            typingpanel.message = ""
            typingpanel.active = False
            typingpanel.refreshMessage()
        else:
            typingpanel.active = True
            typingpanel.refreshMessage()
    elif key.vk == libtcod.KEY_ESCAPE:
        if typingpanel.active:
            typingpanel.active = False
        else:
            return True
    elif typingpanel.active:
        typingpanel.handleKey(key)
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
        player.move(areamap, xdir, ydir)
        areamap.recomputeLights(player)


def render_all(mapdata, player, con):
    for entity in mapdata.entities:
        entity.draw(mapdata.fovMap)
    for y in range(mapdata.height):
        for x in range(mapdata.width):
            key1 = 'dark'
            key2 = 'ground'
            if libtcod.map_is_in_fov(mapdata.fovMap, x, y):
                key1 = 'visible' 
                mapdata.tiles[x][y].explored = True

            if mapdata.tiles[x][y].block_sight: 
                key2 = 'wall'

            if mapdata.tiles[x][y].explored:
                libtcod.console_set_char_background(con, x, y, colors[key1][key2], libtcod.BKGND_SET)
    player.draw(mapdata.fovMap)

def createMonsters(areaMap):
    for room in areaMap.rooms:
        nummonsters = libtcod.random_get_int(0, 0, MAX_ROOM_MONSTERS)
        for i in range(nummonsters):
            x = libtcod.random_get_int(0, room.rect.x1, room.rect.x2)
            y = libtcod.random_get_int(0, room.rect.y1, room.rect.y2)

            if not areaMap.isBlocked(x,y):
                combat_component = CombatObject(hp=10, defense=1, power=1, deathfunction=monster_death)
                ai_component = BasicMonster()
                areaMap.entities.append(Entity(x, y, 'o', libtcod.desaturated_green, 'orc', True, {'combat': combat_component, 'ai': ai_component}))


def show_status(chatcon, player):
    libtcod.console_set_default_foreground(chatcon, libtcod.white)
    hptext = "Dead."
    if player.properties['combat'] is not None:
        hptext = 'HP: ' + str(player.properties['combat'].hp) + '/' + str(player.properties['combat'].max_hp)
    libtcod.console_print_ex(chatcon, 1, 0, libtcod.BKGND_NONE, libtcod.LEFT,
            hptext)

def displayKillMessage(killed, killer):
    combatlog.appendMessage(killer.capitalize() + " killed " + killed + "!")

def player_death(player, killer):
    displayKillMessage(player.name, killer.name)
    print 'You died!'
    player.char = '%'
    player.color = libtcod.dark_red
    player.properties['combat'] = None

def monster_death(monster, killer):
    displayKillMessage(monster.name, killer.name)
    print monster.name.capitalize() + ' is dead!'
    monster.char = '%'
    monster.blocks = False
    monster.properties['combat'] = None
    monster.properties['ai'] = None
    monster.name = 'remains of ' + monster.name
    # TODO : monster send to back

class ServerConnection:
    def __init__(self):
        self.tcpsocket = None
        self.incomingmessages = queue.Queue()
        self.outgoingmessages = queue.Queue()
        self.incomingbuffer = BytesIO()
        self.outgoingbuffer = BytesIO()
        self.ok = False
        self.unpacker = msgpack.Unpacker
        self.packer = msgpack.Packer

    def connect(self, ip, port):
        self.serverip = ip
        self.serverport = port
        if self.tcpsocket is not None:
            self.tcpsocket.close()
        self.ok = False
        self.tcpsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcpsocket.settimeout(5)

        for i in range(TCP_RETRYCOUNT):
            try:
                msgpanel.appendClientMessage('Connecting to ' + ip + ":" + str(port) + "...")
                self.tcpsocket.connect((ip, port))
                msgpanel.appendClientMessage('Connected.')
                self.ok = True
                self.tcpsocket.settimeout(None)
                break
            except socket.timeout:
                msgpanel.appendClientMessage('Timed out.')
                pass
            except socket.error as (errno, msg):
                msgpanel.appendClientMessage('ERROR : ' + msg)
                break

def parsemessages(conn):
    for unpacked in unpacker:
        try:
            conn.incomingmessages.put(unpacked)
        except queue.Full:
            msgpanel.appendClientMessage("INCOMING MESSAGE QUEUE FULL, MUCHOS PROBLEM!!!!!")

def connectionfunc():
    ip = "127.0.0.1"
    port = 5005

    conn = ServerConnection()
    conn.connect(ip, port)
    if not conn.ok:
        return

    conn.tcpsocket.setblocking(False)
    while 1:
        ## check for incoming messages
        try:
            conn.unpacker.feed(conn.tcpsocket.recv()) # need to check the ret?
            parsemessages(self.incomingbuffer)
        except:
            pass

        ## send outgoing messages
        try:
            msg = conn.outgoingmessages.get(False)
            conn.tcpsocket.send(conn.packer.pack(msg))
        except queue.Empty:
            pass



#libtcod.console_set_custom_font('arial.ttf', libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_TCOD)

libtcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, 'python/libtcod tutorial', False)
libtcod.sys_set_fps(LIMIT_FPS)

npc = Entity(SCREEN_WIDTH/2-5, SCREEN_HEIGHT/2, '@', libtcod.yellow, 'npc')
combat_component = CombatObject(hp=20, defense=2, power=5, deathfunction=player_death)
player = Entity(25, 23, '@', libtcod.white, 'player', True, {'combat': combat_component})

con = libtcod.console_new(SCREEN_WIDTH-20, SCREEN_HEIGHT-10)
chatcon = libtcod.console_new(SCREEN_WIDTH, 10)
mapdata = AreaMap(SCREEN_WIDTH, SCREEN_HEIGHT)
mapdata.entities = [npc, player]
createMonsters(mapdata)
mapdata.recomputeLights(player)

msgpanel = MessagePanel(0, SCREEN_HEIGHT-15, SCREEN_WIDTH/2, 10)
combatlog = MessagePanel(SCREEN_WIDTH/2+1, SCREEN_HEIGHT-25, SCREEN_WIDTH/2, 20)
statuspanel = StatusPanel(player)
typingpanel = TypingPanel()


thread = threading.Thread(target = connectionfunc)
thread.start()


while not libtcod.console_is_window_closed():
    libtcod.console_set_default_foreground(con, libtcod.white)

    render_all(mapdata, player, con)
    show_status(chatcon, player)

    libtcod.console_blit(con, 0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, 0, 0, 0)
#    libtcod.console_blit(chatcon, 0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, 0, 0, SCREEN_HEIGHT-10)
    combatlog.display()
    msgpanel.display()
    statuspanel.display()
    typingpanel.display()
    libtcod.console_flush()

    for entity in mapdata.entities:
        entity.clear()

    exit = handle_keys(player, mapdata, typingpanel)
    if exit:
        break

    for o in mapdata.entities:
        if o != player and 'ai' in o.properties:
            o.properties['ai'].takeTurn(mapdata, player) # TODO : timeout for monster
