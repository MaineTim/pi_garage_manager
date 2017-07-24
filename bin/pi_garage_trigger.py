#!/usr/bin/env python
import sys
from multiprocessing.connection import Client

if len(sys.argv) < 2:
    print "You must pass a parameter. (open, close, trigger, away, home, state)"

else:
    address = ('localhost', 6000)
    conn = Client(address, authkey='secret password')
    conn.send_bytes(sys.argv[1])
    print conn.recv_bytes()
    conn.close()
