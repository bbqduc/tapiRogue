SYSTEM_MESSAGE = 0
CHAT_MESSAGE = 1
NEW_CLIENT_CONNECTION = 2
CLIENT_DISCONNECT = 3
PONG = 4
FULL_STATE_MESSAGE = 6
FULL_STATIC_STATE_MESSAGE = 7
CLIENT_CONNECT = 8
MOVEMENT_MESSAGE = 9
DIFF_STATE_MESSAGE = 10
ACTION_MESSAGE = 11

def SystemMessage(msg):
    return { 'type': SYSTEM_MESSAGE,
            'msg': msg
            }

def ChatMessage(sender, msg):
    return { 'type': CHAT_MESSAGE,
                'msg': msg,
                'sender': sender
                }

def DisconnectMessage(entityid):
    return { 'type': CLIENT_DISCONNECT,
            'id': entityid
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

def DiffStateMessage(state):
    return { 'type': DIFF_STATE_MESSAGE,
            'state': state }

def MovementMessage(xdir, ydir):
    return { 'type': MOVEMENT_MESSAGE,
            'xdir': xdir,
            'ydir': ydir}

def ActionMessage(action):
    return { 'type': ACTION_MESSAGE,
            'action': action,
            }
