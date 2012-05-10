#!/usr/bin/env python
# -*- coding: utf-8 -*-

from twisted.internet import reactor, protocol, defer, task
from twisted.protocols.basic import LineReceiver


class LiquidsoapProtocol(LineReceiver):
    def __init__(self):
        self.current_cmd = None
        self.incoming = ""

    def connectionMade(self):
        self.current_cmd = None
        self.incoming = ""
        def _ka():
            if not self.current_cmd:
                self.call('uptime')
        self.keepalive = task.LoopingCall(_ka).start(10)

    def connectionLost(self, reason):
        if self.keepalive:
            self.keepalive.stop()
        if self.current_cmd:
            self.current_cmd.errback(Exception("Connection to Liquidsoap lost"))

    def lineReceived(self, line):
        if not self.current_cmd:
            print 'ERR: recieved "%s", but nothing was requested' % repr(line)
        if line.startswith("END"):
            self.current_cmd.callback(self.incoming)
            self.current_cmd = None
        else:
            self.incoming += line + '\n'

    def call(self, cmd):
        if self.current_cmd:    # TODO: make this async
            raise Exception("command already called")
        self.current_cmd = defer.Deferred()
        self.incoming = ""
        self.sendLine(cmd)
        return self.current_cmd


class LiquidsoapFactory(protocol.ReconnectingClientFactory):
    protocol = LiquidsoapProtocol

    def buildProtocol(self, address):
        p = self.protocol()
        self.instance = p
        return p
