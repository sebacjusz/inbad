#!/usr/bin/env python
import socket, sys, json, readline

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((sys.argv[1], int(sys.argv[2])))
while True:
    i = input('>')
    d = json.dumps(i)
    d = str(len(d)) + ':' + d + ','
    sent=0
    while sent < len(d):
        s = sock.send(d[sent:])
        if s==0:
            raise RuntimeError("disconnected")
        sent += s
    buf = ''
    while ':' not in buf:
        s = sock.recv(6)
        if s=='':
            raise RuntimeError("disconnected")
        buf += s
    cp = buf.index(':')
    inc_len = int(buf[:cp])
    buf = buf[cp+1:]
    rd=len(buf)
    while rd<inc_len+1:
        s = sock.recv(inc_len+1-rd)
        if s=='':
            raise RuntimeError("disconnected")
        buf += s
        rd += len(s)
    if not (len(buf)-1==inc_len and buf[-1]==','):
        raise RuntimeError('recv parse err')
    print json.loads(buf[:-1])

