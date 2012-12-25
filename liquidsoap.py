#!/usr/bin/env python
# -*- coding: utf-8 -*-

from twisted.internet import reactor, protocol, defer, task
from twisted.protocols.basic import LineReceiver
from collections import deque
import json

class LiquidsoapError(Exception):
    def __init__(self, err):
        self.error = err
    def __repr__(self):
        return 'LiquidsoapError(%s)' % self.error

def _checkOK(resp):
    if resp.startswith('ok'):
        return True
    else:
        raise LiquidsoapError(resp)

class LiquidsoapProtocol(LineReceiver):
    def __init__(self):
        self.incoming = ""
        self.queue = deque()

    def connectionMade(self):
        self.current_cmd = None
        self.incoming = ""
        def _ka():
            if not self.current_cmd:
                self.call('uptime')
        self.keepalive = task.LoopingCall(_ka)
        self.keepalive.start(10)

    def connectionLost(self, reason):
        if self.keepalive:
            self.keepalive.stop()
        if self.current_cmd:
            self.current_cmd.errback(Exception("Connection to Liquidsoap lost"))

    def lineReceived(self, line):
        if len(self.queue)==0:
            print 'ERR: recieved "%s", but nothing was requested' % repr(line)
        if line.startswith("END"):
            _,d = self.queue.pop()
            if len(self.queue)>0:
                self.sendLine(self.queue[-1][0])
            # WARNING: callback MUST be called AFTER sending any pending request
            # Otherwise, bad things happen if the callback calls another command.
            d.callback(self.incoming.decode('utf-8'))
            self.incoming = ""
        else:
            self.incoming += line + '\n'

    def call(self, cmd):
        if type(cmd) == unicode:
            cmd = cmd.encode('utf-8')
        d = defer.Deferred()
        self.queue.appendleft((cmd,d))
        if len(self.queue)==1:
            self.sendLine(cmd)
        return d

    def getMixer(self):
        d = self.call("mixer.getdata")
        return d.addCallback(json.loads)
    def setMixer(self, k, v):
        cmd = "mixer.set %s:%f" %(k, float(v))
        return self.call(cmd).addCallback(_checkOK)
    def setMetadataMaster(self, k):
        return self.call('mixer.set_master %s' % k).addCallback(_checkOK)
    def createRequest(self, k):
        return self.call('create_request %s' % k).addCallback(_checkOK)
    def removeMixer(self, k):
        return self.call('mixer.remove %s' % k).addCallback(_checkOK)
    def pushRequest(self, k, url):
        def _check(resp):
            try:
                return int(resp)
            except ValueError:
                raise LiquidsoapError(resp)
        return self.call('%s.push %s' % (k,url)).addCallback(_check)
    def getOutputRMS(self):
        def _check(resp):
            try:
                return float(resp)
            except ValueError:
                raise LiquidsoapError(resp)
        return self.call('final_output.rms').addCallback(_check)

class LiquidsoapFactory(protocol.ReconnectingClientFactory):
    protocol = LiquidsoapProtocol

    def buildProtocol(self, address):
        p = self.protocol()
        self.instance = p
        return p
