import libtcodpy as libtcod
import tapirogueproperties as tapiRogueProperties
import math

class Entity:
    def __init__(self, x, y, char, color, name, entityid, blocks=True, properties={}):
        self.x = x
        self.y = y
        self.char = char
        self.color = color
        self.name = name
        self.blocks = blocks
        self.properties = properties
        self.entityid = entityid
        for p in self.properties:
            self.properties[p].owner = self

    def draw(self, fov, con):
        if libtcod.map_is_in_fov(fov, self.x, self.y):
            libtcod.console_set_default_foreground(con, self.color)
            libtcod.console_put_char(con, self.x, self.y, self.char, libtcod.BKGND_NONE)

    def clear(self, con):
        libtcod.console_put_char(con, self.x, self.y, ' ', libtcod.BKGND_NONE)

    def move(self, areamap, xdir, ydir):
        if not areamap.isBlocked(self.x+xdir, self.y+ydir):
            self.x += xdir
            self.y += ydir
            self.server.diffpacket[self.entityid] = {'x': self.x, 'y' : self.y}
            self.server.changed = True

    def distanceTo(self, x, y):
        dx = x - self.x
        dy = y - self.y
        return math.sqrt(dx ** 2 + dy ** 2)
    
    def AddProperty(self, name, data, module):
        self.properties[name] = CreateProperty(name, data, module)

    def serialize(self):
        props = {}
        for p in self.properties:
            if p != 'basicai':
                props[p] = self.properties[p].serialize()

        return {'x': self.x,
                'y': self.y,
                'char': self.char,
                'color_r': self.color.r,
                'color_g': self.color.g,
                'color_b': self.color.b,
                'name': self.name,
                'id': self.entityid,
                'properties': props
                }
    
def CreateProperty(name, data, module):
    propclass = getattr(tapiRogueProperties, name)
    return propclass(data, module)
