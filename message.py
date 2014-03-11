SYSTEM_MESSAGE = 0
CHAT_MESSAGE = 1
NEW_CLIENT_CONNECTION = 2
CLIENT_DISCONNECT = 3
PONG = 4
FULL_STATE_MESSAGE = 6
FULL_STATIC_STATE_MESSAGE = 7
CLIENT_CONNECT = 8
MOVEMENT_MESSAGE = 9

def SystemMessage(msg):
    return { 'type': SYSTEM_MESSAGE,
            'msg': msg
            }

def ChatMessage(sender, msg):
    return { 'type': CHAT_MESSAGE,
                'msg': msg,
                'sender': sender
                }

def NewClientMessage(socket, name):
    return { 'type': NEW_CLIENT_CONNECTION,
                'socket': socket,
                'name': name
                }

def DisconnectMessage():
    return { 'type': CLIENT_DISCONNECT
                }

def ConnectMessage():
    return { 'type': CLIENT_CONNECT
                }

def FullStateMessage(state):
    return { 'type': FULL_STATE_MESSAGE,
            'state': state }

def FullStaticStateMessage(state):
    return { 'type': FULL_STATIC_STATE_MESSAGE,
            'state': state }

def MovementMessage(xdir, ydir):
    return { 'type': MOVEMENT_MESSAGE,
            'xdir': xdir,
            'ydir': ydir}
