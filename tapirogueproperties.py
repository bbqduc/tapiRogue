class Property:
    def __init__(self, data):
        self.deserialize(data)
    def deserialize(self, data):
        self.__dict__ = data
    def serialize(self):
        return self.__dict__



class combat(Property):
    def __init__(self, data, module):
        Property.__init__(self, data)

        self.deathfuncstring = data['deathfunction']
        if data['deathfunction'] == None:
            self.deathfunction = None
        else:
            self.deathfunction = getattr(module, data['deathfunction'])

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

#    def serialize(self):
 #       self.deathfunction = None
  #      ret = Property.serialize(self).copy
#        ret['deathfunction'] = None #self.deathfuncstring
   #     return ret


class basicai(Property):
    def __init__(self, data):
        Property.__init__(self, data)

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
