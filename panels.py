import libtcodpy as libtcod

class TypingPanel:
    def __init__(self, width, height):
        self.message = ""
        self.x = 1
        self.y = height
        self.width = width
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
        libtcod.console_blit(self.console, 0, 0, self.width, self.height, 0, self.x, self.y)

class StatusPanel:
    def __init__(self, player, x, y):
        self.player = player
        self.x = x
        self.y = y 
        self.width = 10
        self.height = 10
        self.console = libtcod.console_new(self.width, self.height)

    def display(self):
        libtcod.console_set_default_foreground(self.console, libtcod.white)
        hptext = "Dead."
        if self.player.properties['combat'] is not None:
            hptext = 'HP: ' + str(self.player.properties['combat'].hp) + '/' + str(self.player.properties['combat'].max_hp)
        libtcod.console_print_ex(self.console, 1, 0, libtcod.BKGND_NONE, libtcod.LEFT, ('{0: <' + str(self.width) + '}').format(hptext))
        libtcod.console_blit(self.console, 0, 0, self.width, self.height, 0, self.x, self.y)

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

    def appendMessage(self, msg): # TODO : compact repeating messages with (x16) etc, necessary?, concurrency
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
        libtcod.console_blit(self.console, 0, 0, self.width, self.height, 0, self.x, self.y)
