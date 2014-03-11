import libtcodpy as libtcod

FOV_ALGO = 0
FOV_LIGHT_WALLS = True
TORCH_RADIUS = 10

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

        self.clear()
        self.rooms = []

        self.calculateFovMap()
        self.entities = []

    def clear(self):
        self.rooms = []
        self.tiles = [[ Tile(True)
            for y in range(self.height) ]
            for x in range(self.width) ]

    def calculateFovMap(self):
        self.fovMap = libtcod.map_new(self.width, self.height)
        for y in range(self.height):
            for x in range(self.width):
                libtcod.map_set_properties(self.fovMap, x, y, not self.tiles[x][y].block_sight, not self.tiles[x][y].blocked)

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
    
    def syncStaticsFromFullState(self, state):
        self.clear()
        for room in state['rooms']:
            self.makeRoom(Rect(room['x1'], room['y1'], room['width'], room['height']))
        for tunnel in state['htunnels']:
            self.makeHorizontalTunnel(tunnel['x1'], tunnel['x2'], tunnel['y'], tunnel['width'])
        for tunnel in state['vtunnels']:
            self.makeVerticalTunnel(tunnel['y1'], tunnel['y2'], tunnel['x'], tunnel['width'])
        self.htunnels = state['htunnels']
        self.vtunnels = state['vtunnels']

        self.calculateFovMap()

    def serialize(self):
        ret = {'rooms': [], 'htunnels':self.htunnels, 'vtunnels':self.vtunnels}
        for room in self.rooms:
            ret['rooms'].append({'x1': room.rect.x1-1, 'y1': room.rect.y1-1, 'width': room.rect.width, 'height': room.rect.height})

        return ret


class Rect:
    def __init__(self, x, y, w, h):
        self.x1 = x
        self.x2 = x+w
        self.y1 = y
        self.y2 = y+h
        self.width = w
        self.height = h
