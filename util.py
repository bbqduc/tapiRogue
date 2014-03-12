import os
import time

if os.name == 'posix':
    clock = time.time
else:
    clock = time.clock

