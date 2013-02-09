#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import division
from twisted.web import server, client
from txjsonrpc.web import jsonrpc
from twisted.internet import reactor, protocol, defer, task
from twisted.application import service, internet
import os, time, random, json
from collections import defaultdict
import datetime
import inba_cfg as conf
from irc import IRCFactory
import icecast
from liquidsoap import *
from util import *
from controller import *
from www import WebInterface
import json


class radioctl(jsonrpc.JSONRPC):
    def __init__(self, service):
        jsonrpc.JSONRPC.__init__(self)
        self.service = service
        self.allowNone = True

    def jsonrpc_authdj(self,user,pwd):
        return self.service.auth(user,pwd)

    def _getFunction(self, path):
        f = getattr(self, "jsonrpc_%s" % path, None)
        if f:
            return f
        else:
            def _fun(*d):
                self.service.event_pub(path, *d)
            return _fun


class RCPSService(service.MultiService):
    def __init__(self):
        service.MultiService.__init__(self)
        self.metalog=open('/dev/null', 'a')
        self.poller = icecast.IcecastPoller(conf.ICE_MOUNT, conf.ICE_SERVERS)
        self.poller.setServiceParent(self)
        self.event_callbacks = defaultdict(list)
        self.meta = None
        self.meta_fmt = MetaFormatter(self)
        self.ircf = []
        self.subscribe('new_track', self._metadataChanged)
        self.subscribe('rec_stopped', self._recordingFinished)

    def startService(self):
        self.statlog = open(conf.STATLOG, 'a')
        print >>self.statlog, '\n'
        task.LoopingCall(self.logStat).start(30)
        service.MultiService.startService(self)

    def subscribe(self, event, f):
        if not f or not callable(f):
            raise TypeError("%s is not callable" % repr(f))
        self.event_callbacks[event].append(f)

    def event_pub(self, event, *args):
        print 'event: %s(%s)' % (event, repr(args))
        for f in self.event_callbacks[event]:
            if not f or not callable(f):
                self.event_callbacks[event].remove(f)
            else:
                f(*args)

    def getJSONResource(self):
        return radioctl(self)

    def getIRCFactory(self, chan):
        f = IRCFactory()
        f.channel = chan
        f.nickname = conf.IRC_NICK
        f.svc = self
        self.ircf.append(f)
        return f

    def getLSFactory(self):
        f = LiquidsoapFactory()
        self.lsf = f
        return f
    
    def getControllerFactory(self):
        f = ControllerFactory(self)
        return f

    def getWWWFactory(self):
        self.wwwf = WebInterface(self)
        return self.wwwf

    def auth(self, user, pwd):
        if (user == 'peja' and pwd == 'tibia') or (user=='dj' and pwd=='papadens'):
            return True
        else: return False

    def _metadataChanged(self, d):
        self.meta = d
        #self.meta = self.poller.get(conf.ICE_MOUNT.keys()[0])
        return
        if self.meta:
            self.logMetadata()
    
    def getListenerCount(self, mode='all', absolute=False):
        if mode=='servers':
            if absolute:
                return {k: v['_listeners'] for k,v in self.poller.server_data.iteritems()}
            else:
                ret = {k:0 for k in conf.ICE_SERVERS}
                for mount in self.poller.values():
                    for k,v in mount['relays'].iteritems():
                        ret[k] += v
                return ret
        elif mode=='total':
            return sum(self.getListenerCount('servers', absolute).values())
        else:
            return {k: v['relays'] for k,v in self.poller.iteritems()}

    def fuzzyQueue(self, k, q):
        if '..' in q or sum(1 for i in q if i=='/')>5:
            raise Exception('ale papierza pawlaka wielkiego polaka to ty szanuj')
        def _match(path, lq):
            x,sep,xs = lq.partition('/')
            ld = os.listdir(path)
            if x in ld:     # exact
                ld = [x] 
            for i in ld:
                if x.lower() in i.lower():
                    if sep and os.path.isdir(path+i):
                        return _match(path+i+'/', xs)
                    if not sep and os.path.isfile(path+i):
                        return path+i
            return None
        m = _match(conf.MP3_DIR, q)
        if m:
            return self.lsf.instance.pushRequest(k, m)

    def getListenURL(self, mount):
        srv_all = [conf.ICE_MOUNT[mount][0]] + conf.ICE_MOUNT[mount][1].keys()
        srv_l = {k:v for k,v in self.getListenerCount('servers',True).items() if k in srv_all}
        srv_w = {k:1 - (v/conf.ICE_LIMITS[k]) for k,v in srv_l.items()}
        tot = sum(srv_w.values())
        r = random.uniform(0, tot - 0.01)
        csum=0
        for k,v in srv_w.items():
            if csum+v >= r:
                if k == conf.ICE_MOUNT[mount][0]:
                    return 'http://'+k+mount
                else:
                    return 'http://'+k+conf.ICE_MOUNT[mount][1][k]
            csum += v
        assert False

    def _recordingFinished(self, path):
        t = time.strftime('-%H:%M:%S')
        pnew = path.replace('(live)', t)
        os.rename(path, pnew)
        print 'moved rec', path, 'to', pnew

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
        print >>self.statlog, int(time.time()), json.dumps(self.getListenerCount('all'))
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
for h,c in conf.IRC_CHANNELS.iteritems():
    internet.TCPClient(h, 6667, s.getIRCFactory(c)).setServiceParent(serviceCollection)
internet.TCPClient('localhost', 1234, s.getLSFactory()).setServiceParent(serviceCollection)
#internet.TCPServer(8010, server.Site(s.getWebResource())).setServiceParent(serviceCollection)
internet.TCPServer(8002, s.getControllerFactory()).setServiceParent(serviceCollection)
internet.TCPServer(8010, s.getWWWFactory()).setServiceParent(serviceCollection)
