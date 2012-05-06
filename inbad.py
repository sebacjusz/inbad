#!/usr/bin/env python
# -*- coding: utf-8 -*-
from twisted.web import server, client, resource
from txjsonrpc.web import jsonrpc
from twisted.internet import reactor, protocol, defer, task
from twisted.application import service, internet
import os, time
from collections import deque, defaultdict
import datetime
import inba_cfg as conf
from irc import IRCFactory
import icecast
from liquidsoap import *
from util import *


class radioctl(jsonrpc.JSONRPC):
    def __init__(self, service):
        jsonrpc.JSONRPC.__init__(self)
        self.service = service
        self.allowNone = True

    def jsonrpc_server_sourceDisconnected(self):
        self.service.streamEnded()
    def jsonrpc_server_sourceConnected(self):
        self.service.streamStarted()


class RCPSService(service.MultiService):
    def __init__(self):
        service.MultiService.__init__(self)
        self.metalog=open('/dev/null', 'a')
        self.poller = icecast.IcecastPoller(conf.ICE_MOUNT, conf.ICE_SERVERS)
        self.poller.setServiceParent(self)
        self.event_callbacks = defaultdict(list)
        self.subscribe('metadata_changed', self._metadataChanged)
        self.meta = None
        self.meta_fmt = MetaFormatter(self)

    def startService(self):
        self.statlog = open(conf.STATLOG, 'a')
        print >>self.statlog, '\n'
        #task.LoopingCall(self.logStat).start(30)
        service.MultiService.startService(self)

    def subscribe(self, event, f):
        if not f or not callable(f):
            raise TypeError("%s is not callable" % repr(f))
        self.event_callbacks[event].append(f)

    def event_pub(self, event, *args):
        print 'event: %s' % event
        for f in self.event_callbacks[event]:
            if not f or not callable(f):
                self.event_callbacks[event].remove(f)
            else:
                f(*args)

    def getJSONResource(self):
        return radioctl(self)

    def getIRCFactory(self):
        f = IRCFactory()
        f.channel = conf.IRC_CHANNEL
        f.nickname = conf.IRC_NICK
        f.svc = self
        self.ircf = f
        return f

    def getLSFactory(self):
        f = protocol.ReconnectingClientFactory()
        f.protocol = LiquidsoapProtocol

    def _metadataChanged(self):
        self.meta = self.poller.get(conf.ICE_MOUNT.keys()[0])
        return
        if self.meta:
            self.logMetadata()

    def streamStarted(self):
        self.listener_peak=0
        self.event_pub('dj_connected')
        return  ##################
        if os.path.exists(conf.REC_TMP):
            os.unlink(conf.REC_TMP)
        client.downloadPage(conf.REC_STREAM, conf.REC_TMP)
        self.rec_start = time.time()
        self.recpath = time.strftime("%Y/%m.%d/", time.localtime(self.rec_start))
        tpath = conf.REC_TARGETDIR +self.recpath
        if not os.path.isdir(tpath):
            os.makedirs(tpath, 0755)
            os.chmod(tpath, 0755)
        if not self.metalog.closed:
            self.metalog.close()
        self.metalog=open(tpath+'tracklist.txt', 'a')
        os.chmod(tpath+'tracklist.txt', 0644)
        def anuncjo(_):
            self.ircf.connectedProto.c_np('', self.ircf.channel, '')
            self.logMetadata(True)
        reactor.callLater(1, lambda : self.updateMetadata().addCallback(anuncjo))
    def streamEnded(self):
        self.event_pub('dj_disconnected')
        return  #############
        self.ircf.connectedProto.notice(self.ircf.channel, '\x034 koniec inby, wasze kwejk.fm tam-->')
        self.ircf.connectedProto.say(self.ircf.channel,
                'najwięcej słuchało \x02 %d \x02 anonków' % self.listener_peak)
        tname = time.strftime("%H:%M-", time.localtime(self.rec_start)) + time.strftime("%H:%M.ogg")
        os.rename(conf.REC_TMP, conf.REC_TARGETDIR + self.recpath+tname)
        os.chmod(conf.REC_TARGETDIR + self.recpath+tname, 0644)
        self.ircf.connectedProto.say(self.ircf.channel, 'nagranie: %s' % (conf.REC_HOSTPATH + self.recpath+tname))
        self.logMetadata()
        reactor.callLater(60, (lambda f: f.close() if not f.closed else None), self.metalog)
        self.ezstream.signalProcess('KILL')
        self.ffmpeg.signalProcess('KILL')

    def logStat(self):
        m=self.metadata.get('dj')
        if not m or not m.has_key('listeners') or not m.has_key('relays'):
            return
        ll = [('pawlacz.tk:8000', m['listeners']-len(m['relays']))] + m['relays']
        ss = sum(i[1] for i in ll)
        self.listener_peak = ss if ss > self.listener_peak else self.listener_peak
        print >>self.statlog, int(time.time()), ' '.join( '|'.join(map(str,i)) for i in ll )
        self.statlog.flush()
    
    def logMetadata(self, no_check=0):
        lm=self.lastmeta.get('dj')
        mm=self.metadata.get('dj')
        if self.metalog.closed or not lm or not mm:
            return
        g_nd = lambda x: dict( (i, x.get(i, '')) for i in ('server_name', 'server_description') )
        g_at = lambda x: dict( (i, x.get(i, '')) for i in ('artist', 'title') )
        mm_t=g_nd(mm)
        if mm_t != g_nd(lm) or no_check:
            print >>self.metalog, time.strftime("%H:%M\t"), (mm_t['server_name'] + (' (%s)' % mm_t['server_description']) if mm_t['server_description'] else '').encode('utf-8')
        mm_t=g_at(mm)
        if mm_t != g_at(lm) or no_check:
            td = str(datetime.timedelta(seconds=int(time.time() - self.rec_start))) + '\t'
            _tmp = u"%s - %s" % (mm_t['artist'], mm_t['title'])
            print >>self.metalog, td, _tmp.encode('utf-8')
        self.metalog.flush()


application=service.Application('inbad')
s = RCPSService()
serviceCollection = service.IServiceCollection(application)
s.setServiceParent(serviceCollection)
internet.TCPServer(8005, server.Site(s.getJSONResource()), interface='127.0.0.1').setServiceParent(serviceCollection)
internet.TCPClient('pawlacz.6irc.net', 6667, s.getIRCFactory()).setServiceParent(serviceCollection)
internet.TCPClient('localhost', 1234, s.getLSFactory()).setServiceParent(serviceCollection)
#internet.TCPServer(8010, server.Site(s.getWebResource())).setServiceParent(serviceCollection)
