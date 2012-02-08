#!/usr/bin/env python
# -*- coding: utf-8 -*-
from twisted.web import xmlrpc, server, client, resource
from twisted.internet import reactor, protocol, defer, task
from twisted.application import service, internet
from twisted.words.protocols import irc
import tempfile, os, time, random,signal,sys, re
from lxml import etree
from collections import deque
import json
client.HTTPClientFactory.noisy = False      #get rid of that 'starting factory' log flood
import inba-cfg as conf
#filters=['gain', '-3', 'mcompand', '0.005,0.1 -47,-40,-34,-34,-17,-33', r'100', r'0.003,0.05 -47,-40,-34,-34,-17,-33', '400',
#		'0.000625,0.0125 -47,-40,-34,-34,-15,-33', '1600', '0.0001,0.025 -47,-40,-34,-34,-31,-31,-0,-30', '6400', '0,0.025 -38,-31,-28,-28,-0,-25',
#		'gain', '15', 'highpass', '22', 'highpass', '22', 'sinc', '-n', '255', '-b', '16', '-17500', 'gain' '9', 'lowpass', '-1', '17801']

class IRCBot(irc.IRCClient):
    def __init__(self):
        self.bvars={'s':self, 'svc':self.factory.srv,
                'Y': lambda f: (lambda x: x(x))(lambda y: f(lambda *args: y(y)(*args))) } #super ycombinator kurwo
        self.bvars.update(globals())
        #self.bvars = dict( (k, self.bvars[k]) for k in self.bvars if not k == k.upper() )
        del self.bvars['conf']  #nie dla psa hasla
        self.bvars['msg_cb']={}
        self.authed_users=set()
        self.last_cmd=time.time()
        self.commands = { '!np': self.c_np,
                            '!gra': self.c_np,
                            '!ile': self.c_ile,
                            '!sile': lambda u,c,a: self.say(c, self.factory.srv.metadata['selekt']['listeners']) }
        self.su_commands = { '!eval': self.c_eval,
                                '!set': self.c_set,
                                '!setcmd': lambda u,c,a: self.c_set(u,c,a, True),
                                '!setcb': lambda u,c,a: self.c_set(u,c,a, False, True) }

    def c_ile(self, user, channel, args):
        m = self.factory.srv.metadata.get('dj')
        if not m:
            self.say(channel, 'offline')
        ll = [('pawlacz.tk:8000', int(m['listeners'])-len(m['relays']))] + m['relays']
        msg = '+ '.join(u'\x033%s\x03:\x034 %d\x03 ' % i for i in ll)
        msg += u', razem słucha \x02%d\x02 anonków.' % sum(i[1] for i in ll)
        return self.say(channel, msg.encode('utf-8'))
    def c_np(self, user, channel, args):
        md = self.factory.srv.metadata
        if md['dj'] and not args=='selekt':
            ii=md['dj']
            s=u"\x02\x034%s\x03\x02%s właśnie nakurwia: \x02%s\x02 - %s" %\
                (ii.get('server_name',''), ("(\x039%s\x03)" % ii['server_description'] if 'server_description' in ii else ''),
                        ii.get('artist', ''), ii.get('title', ''))
            return self.say(channel, s.encode('utf-8'))
        elif conf.SELEKT_ENABLE:
            ii=md['selekt']
            s=u"\x02\x034RCP Selekt\x03\x02 właśnie nakurwia:\x039 %s\x03%s" %\
                (ii['file'].split('/')[-1], ( ("\x02 %s\x02 - %s" % (ii.get('artist', ''), ii['title'])) if 'title' in ii else ''))
            return self.say(channel, s.encode('utf-8'))
        else:
            return self.say(channel, u'nie ma inby, kłapołech zjat.'.encode('utf-8'))

    def c_eval(self, user, channel, args):
        try:
            ev = eval(args, self.bvars)
            return self.say(channel, unicode(ev).encode('utf-8'), conf.MAXLEN)
        except:
            return self.say(channel,"\x02\x034%s" % repr(sys.exc_info()[1]))

    def c_set(self, user, chan, args, assign_cmd=False, msg_cb=False):
        if not args:
            return self.say(chan, ("known terms: %s" % ','.join(map(unicode, self.bvars))).encode('utf-8'), conf.MAXLEN)
        al = args.split(None, 1)
        if len(al)==1:  #display value
            if al[0] in self.bvars:
                self.say(chan, unicode(self.bvars[al[0]]).encode('utf-8'), conf.MAXLEN)
            else:
                self.say(chan, 'variable not found')
        else:
            try:
                if msg_cb:
                    t =eval(args, self.bvars)
                    if type(t[0]) == str and callable(t[1]):
                        self.bvars['msg_cb'][t[0]]=(re.compile(t[0], re.IGNORECASE), t[1])
                    else:
                        return self.say(chan, '\x034err\x03')
                else:
                    t =eval(al[1], self.bvars)
                    self.bvars[al[0]] = t
                    if assign_cmd:
                        if callable(t):
                            self.commands['!'+al[0]]=t
                        else:
                            return self.say(chan, '\x034 %s is not callable\x03' % str(type(t)))
                self.say(chan, '\x033ok\x03')
            except:
                self.say(chan,"\x02\x034%s" % repr(sys.exc_info()[1]))

    def signedOn(self):
        self.msg('nickserv', 'identify ' + conf.NICKSERV_PASS)
        self.join(self.factory.channel)
    def connectionMade(self):
        self.nickname = self.factory.nickname
        irc.IRCClient.connectionMade(self)
    def userLeft(self, user, channel):
        user = user.split('!', 1)[0]
        self.authed_users.discard(user)
    def userQuit(self, user, qmsg):
        user = user.split('!', 1)[0]
        self.authed_users.discard(user)

    def privmsg(self, user, channel, msg):
        user = user.split('!', 1)[0]
        _tmp = msg.split(None, 1)
        c, args = _tmp if len(_tmp)>1 else (_tmp[0], None)
        if c in self.su_commands and user in self.authed_users:
            return self.su_commands[c](user,channel,args)
        elif c in self.commands:
            if time.time() - self.last_cmd > 2:
                self.last_cmd = time.time()
                return self.commands[c](user,channel,args)
        elif channel == self.nickname:
            al=args.split()
            if c == 'auth' and len(al)==1:
                pwd = al[0]
                print 'auth', user, 'pwd:', pwd
                if user in self.authed_users:
                    return self.msg(user, "juz zalogowan'd co")
                elif user in conf.ACL and pwd == conf.ACL[user]:
                    self.authed_users.add(user)
                    return self.msg(user, 'ok')
                else:
                    return self.msg(user, 'zle, wykurwiaj')
            elif c == 'deauth': 
                if user in self.authed_users:
                    self.authed_users.discard(user)
                    return self.msg(user, 'ok')
        for k in self.bvars['msg_cb']:
            it=self.bvars['msg_cb'][k]
            if it[0].match(msg):
                return it[1](user, msg, it[0].findall(msg))

class radioctl(xmlrpc.XMLRPC):
    def __init__(self, service):
        xmlrpc.XMLRPC.__init__(self)
        self.service = service
        self.allowNone=True
    def xmlrpc_getNextTrack(self):
        return self.service.nextTrack()
    def xmlrpc_q_skip(self):
        if not conf.SELEKT_ENABLE: raise xmlrpc.Fault('offline', '')
        self.service.skip()
    def xmlrpc_q_add(self, it):
        if not conf.SELEKT_ENABLE: raise xmlrpc.Fault('offline', '')
        self.service.add(it)
    def xmlrpc_q_list(self):
        if not conf.SELEKT_ENABLE: raise xmlrpc.Fault('offline', '')
        return self.service.tracklist()
    def xmlrpc_q_np(self):
        if not conf.SELEKT_ENABLE: raise xmlrpc.Fault('offline', '')
        return self.service.nowplaying
    def xmlrpc_server_sourceDisconnected(self):
        self.service.streamEnded()
    def xmlrpc_server_sourceConnected(self):
        print '_rpc_connected'
        self.service.streamStarted()


def _add_out_callbacks(d, r):
    d.addCallback(json.dumps, separators=(',',':'))
    d.addCallback(r.write)
    return d.addCallback(lambda _: r.finish())


class WebLongPoll(resource.Resource):
    def __init__(self, stream, service):
        self.service = service
        self.stream=stream
    def render_GET(self, request):
        d = self.service.lp_getMetadata(self.stream)
        d.addCallback(lambda x: dict((k,x[k]) for k in x if k in conf.safe_params ))
        _add_out_callbacks(d, request)
        return server.NOT_DONE_YET

class WebJSONInfo(resource.Resource):
    def __init__(self, service):
        resource.Resource.__init__(self)
        self.service=service
        self.putChild("", self)
        self.putChild("m", self)
        self.putChild("longpoll_selekt", WebLongPoll('selekt', service))
        self.putChild("longpoll_dj", WebLongPoll('dj', service))

    def render_GET(self, request):
        d = defer.Deferred()
        d.addCallback(lambda y: dict((o_k, dict((k,y[o_k][k]) for k in y[o_k] if k in conf.safe_params ) ) for o_k in y if y[o_k]))
        _add_out_callbacks(d, request)
        d.callback(self.service.metadata)
        return server.NOT_DONE_YET


class IcesProtocol(protocol.ProcessProtocol):
    def processEnded(self, reason):
        if conf.SELEKT_ENABLE:
            print 'ices2 died, exiting...', reason
            return reactor.stop()

class SoxProtocol(protocol.ProcessProtocol):
    def __init__(self, pipe):
        self.out_pipe=pipe
    def processEnded(self, reason):
        #print 'pr_ended'
        return reactor.callLater(30, os.unlink, self.out_pipe)
    def die(self):
        print 'die:', self.transport.pid
        if self.transport.pid:
            self.transport.signalProcess('KILL')

class IRCFactory(protocol.ReconnectingClientFactory):
    protocol = IRCBot
    def buildProtocol(self, address):
        proto = protocol.ReconnectingClientFactory.buildProtocol(self, address)
        self.connectedProto = proto
        return proto

class RCPSService(service.Service):
    def __init__(self, ices_args):
        self.current_sox=None
        self.queue=deque()
        self.nowplaying=''
        self.jng_lastago=1
        self.ices_args=ices_args
        self.metadata={}
        self.listener_peak=0
        self.lastmeta={'selekt':{}, 'dj': {} }
        self.lp_defers={'selekt':[], 'dj':[]}
        self.metalog=open('/dev/null', 'a')
        self.metaupdater=None
        print 'sinit'
    def _runUpdater(self):
        if self.metaupdater and self.metaupdater.running:
            self.metaupdater.stop()
        self.metaupdater=task.LoopingCall(self.updateMetadata)
        self.metaupdater.start(2)   
    def startService(self):
        if conf.SELEKT_ENABLE:
            self.startSelekt()
        reactor.callLater(5, lambda: self._runUpdater())    #give ices time to start
        self.statlog = open(conf.STATLOG, 'a')
        print >>self.statlog, '\n'
        task.LoopingCall(self.logStat).start(30)
        service.Service.startService(self)
        print 'estart'

    def startSelekt(self):
        global conf.SELEKT_ENABLE
        conf.SELEKT_ENABLE=True;
        pp=IcesProtocol()
        self.ices=reactor.spawnProcess(pp, '/usr/bin/ices2', self.ices_args, env=None)
        print 'spawned ices'

    def stopSelekt(self):
        global conf.SELEKT_ENABLE
        self.ices.signalProcess('TERM')
        self.current_sox.proto.die()
        conf.SELEKT_ENABLE=False;

    def nextTrack(self):
        "Create a new named pipe, spawn a new sox process outputting to it and return the path of that pipe. This is blocking."
        if self.current_sox and self.current_sox.proto:
            reactor.callLater(10, self.current_sox.proto.die) #make sure it dies
        fifon=tempfile.mktemp(prefix='RCP%s'%int(time.time()))
        os.mkfifo(fifon)
        if self.jng_lastago > random.randint(0, 5):
            self.jng_lastago=0
            mp3=conf.jng_dir+random.choice(conf.jng_list)
        else:
            self.jng_lastago+=1
            if len(self.queue)>0:
                mp3=self.queue.pop()
            else:
                mp3=conf.SELEKT_IDLE_TRACK
        self.nowplaying=mp3
        cmd=['sox', mp3, '-t', 'vorbis', '-c', '2', '-r', '44100', fifon]+conf.filters
        print mp3, fifon, ' '.join(cmd)
        sp=SoxProtocol(fifon)
        self.current_sox=reactor.spawnProcess(sp, 'sox', cmd)
        return fifon

    def skip(self):
        self.ices.signalProcess('HUP')
    def tracklist(self):
        return list(self.queue)
    def add(self, it):
        if type(it) == list:
            map(self.queue.appendleft, it)
        else:
            self.queue.appendleft(it)

    def lp_getMetadata(self, stream):
        if stream not in ('selekt', 'dj'):
            raise Exception("invalid stream name")
        d = defer.Deferred()
        self.lp_defers[stream].append(d)
        return d

    def getXRResource(self):
        return radioctl(self)
    def getWebResource(self):
        return WebJSONInfo(self)
    def getIRCFactory(self):
        f = IRCFactory()
        f.channel = '#karachan'
        f.nickname = "jan_kontroler_drugi"
        f.srv=self
        self.ircf = f
        return f

    def getStreamMetadata(self, server, auth):
        basicAuth = ('%s:%s' % auth).encode('base64')
        authHeader = "Basic " + basicAuth.strip()
        d = client.getPage('http://' + server + '/admin/stats', headers={"Authorization": authHeader})
        d.addCallback(lambda x: etree.fromstring(x))
        def parse_data(tree):
            return dict([(i.attrib['mount'], dict([(j.tag, j.text) for j in i])) for i in tree.iter('source')])
        return d.addCallback(parse_data)

    def _metadataChanged(self, n):
        print '_____meta changed (%s)________, defers:' % n, self.lp_defers[n]
        for j in self.lp_defers[n]:
            j.callback(self.metadata[n])
        if n=='dj':
            self.logMetadata()
        self.lastmeta[n] = self.metadata[n]
        self.lp_defers[n]=[]
    def updateMetadata(self):
        def f(l):
            dj, sel = (l.get('/stream.ogg', {}), l.get('/selekt.ogg', {}))
            self.metadata = {'dj':dj, 'selekt': sel}
            def f2(trash=None):
                for i in self.metadata:
                    if not self.metadata[i]:
                        for j in self.lp_defers[i]:
                            j.cancel()
                    filt = (lambda d: dict( (k, d[k]) for k in d if k in ('artist', 'title', 'file', 'server_description', 'server_name')))\
                            if i != 'selekt' else lambda d: {'file':d['file']}
                    elif filt(self.metadata[i]) != filt(self.lastmeta[i]):
                        self._metadataChanged(i)
            if dj:
                self.metadata['dj']['relays']=[]
                dl=[]
                mp3 = l.get('/stream.mp3')
                if mp3 and mp3.has_key('listeners'):    #biedacki hack
                    self.metadata['dj']['relays'].append( ('pawlacz(mp3)', int(mp3['listeners'])) )
                for addr in conf.RELAYS:
                    rel = self.getStreamMetadata(addr['host'], addr['auth'])
                    def _append_count(m, rel_i):
                        if rel_i['mount'] in m:
                            self.metadata['dj']['relays'].append( (rel_i['host'], int(m[rel_i['mount']]['listeners'])) )
                    rel.addCallback(_append_count, rel_i=addr.copy())
                    dl.append(rel)
                def _eb(e):
                    print "____________EEEE:" + repr(e)
                return defer.DeferredList(dl).addBoth(f2).addErrback(_eb)
            else:
                return f2()
        return self.getStreamMetadata(*conf.MASTER_ICECAST).addCallback(f)

    def streamStarted(self):
        print 'sstarted'
        self.listener_peak=0
        def anuncjo(_):
            self.ircf.connectedProto.c_np('', self.ircf.channel, '')
        reactor.callLater(1, lambda : self.updateMetadata().addCallback(anuncjo))
        self.ircf.connectedProto.notice(self.ircf.channel, "DJ połączon'd, nakurwiam nagranie und stream mp3")
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
        self.ffmpeg = reactor.spawnProcess(protocol.ProcessProtocol(), '/usr/bin/ffmpeg', ('ffmpeg', '-i',conf.REC_STREAM,
                                        '-f', 'mp3', '-b', '64k', '-ac', '2', '-y', conf.MP3_PIPE))
        self.ezstream = reactor.spawnProcess(protocol.ProcessProtocol(), '/usr/bin/ezstream', ('ezstream', '-c', '/anon/rcp/ezstream_reencode_mp3.xml'))
    def streamEnded(self):
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
        ll = [('pawlacz.tk:8000', int(m['listeners'])-len(m['relays']))] + m['relays']
        ss = sum(i[1] for i in ll)
        self.listener_peak = ss if ss > self.listener_peak else self.listener_peak
        print >>self.statlog, int(time.time()), ' '.join( '|'.join(map(str,i)) for i in ll )
        print int(time.time()), ' '.join( '|'.join(map(str,i)) for i in ll )
        self.statlog.flush()
    
    def logMetadata(self, no_check=0):
        lm=self.lastmeta.get('dj')
        mm=self.metadata.get('dj')
        if self.metalog.closed or not lm or not mm:
            return
        g_nd = lambda x: dict( ( (k, x[k]) for k in x.iterkeys() if k == 'server_name' or k == 'server_description') )
        g_at = lambda x: dict( (  (i, x.get(i, '')) for i in ('artist', 'title') ) )
        if g_nd(mm) != g_nd(lm) or no_check:
            print >>self.metalog, time.strftime("%H:%M\t"), mm['server_name'] + (' (%s)' % mm['server_description']) if mm['server_description'] else ''
        mm_t=g_at(mm)
        if mm_t != g_at(lm) or no_check:
            td = time.strftime("%H:%M:%S\t", time.localtime(time.time() - self.rec_start))
            print >>self.metalog, td, "%s - %s\n" % (mm_t['artist'], mm_t['title'])
        self.metalog.flush()


application=service.Application('inbad')
s = RCPSService(['ices2','/anon/rcp/ices-script.xml'])
serviceCollection = service.IServiceCollection(application)
s.setServiceParent(serviceCollection)
internet.TCPServer(8005, server.Site(s.getXRResource()), interface='127.0.0.1').setServiceParent(serviceCollection)
internet.TCPClient('127.0.0.1', 6667, s.getIRCFactory()).setServiceParent(serviceCollection)
internet.TCPServer(8010, server.Site(s.getWebResource())).setServiceParent(serviceCollection)
