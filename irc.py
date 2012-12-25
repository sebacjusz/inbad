#!/usr/bin/env python
# -*- coding: utf-8 -*-

from twisted.internet import reactor, protocol, defer
from twisted.words.protocols import irc
import sys
import re
import time
import inba_cfg as conf
from util import *


class IRCBot(irc.IRCClient):
    def __init__(self, factory):
        self.factory = factory
        self.bvars = {'ii': self, 'svc': factory.svc,
                'Y': lambda f: (lambda x: x(x))(lambda y: f(lambda *args: y(y)(*args)))}    # super ycombinator kurwo
        self.bvars.update(globals())
        del self.bvars['conf']  # nie dla psa hasla
        self.bvars['msg_cb'] = {}
        self.authed_users = set()
        self.last_cmd = time.time()
        self.factory.svc.subscribe('metadata_changed', lambda: self.c_np('', '#vichan', ''))
        self.commands = {'!gra': self.c_np,
                            '!ile': self.c_ile}
        self.su_commands = {'!eval': self.c_eval,
                                '!set': self.c_set,
                                '!setcmd': lambda u,c,a: self.c_set(u,c,a, True),
                                '!setcb': lambda u,c,a: self.c_set(u,c,a, False, True)}

    def c_ile(self, user, channel, args):
        if args and '-all' in args:
            m = self.factory.svc.getListenerCount()
            m_mount = lambda d: (u'\x034%s\x03: '%d) + ','.join(u'%s:\x033 %d\x03'%(k.split(':')[0],v) for k,v in m[d].iteritems())
            msg = ' |'.join(m_mount(i) for i in m)
        else:
            m = self.factory.svc.getListenerCount('servers')
            msg = '| '.join(u'\x034%s\x03:\x033 %d\x03' % (k.split(':')[0], v) for k,v in m.iteritems())
        msg += u'\nrazem słucha \x02%d\x02 anonków.' % self.factory.svc.getListenerCount('total')
        return self.say(channel, msg.encode('utf-8'))

    def c_np(self, user, channel, args):
        msg = self.factory.svc.meta_fmt(fmt=MetaFormatter.IRC, track=True,
                s_name=True, s_desc=True, notify_offline=True, time_fmt=None)
        return self.say(channel, msg.encode('utf-8'))
        ##############
        md = self.factory.svc.meta
        if not md:
            return self.say(channel, u'nie ma inby, kłapołech zjat.'.encode('utf-8'))
        s = u"\x02\x034%s\x03\x02%s właśnie nakurwia: \x02%s\x02 - %s"
        desc=''
        if md['server_description']:
            desc = u"(\x039%s\x03)" % md['server_description']
        msg = s % (md.get('server_name'), desc, md.get('artist'), md.get('title'))

    def c_eval(self, user, channel, args):
        try:
            ev = eval(args, self.bvars)
            if isinstance(ev,defer.Deferred):
                def _ff(*l):
                    if len(l)>2:
                        s = unicode(l)
                    else:
                        s=unicode(l[0])
                    self.say(channel, s.encode('utf-8'), conf.MAXLEN)
                return ev.addCallback(_ff)
            return self.say(channel, unicode(ev).encode('utf-8'), conf.MAXLEN)
        except:
            return self.say(channel, "\x02\x034%s" % repr(sys.exc_info()[1]))

    def c_set(self, user, chan, args, assign_cmd=False, msg_cb=False):
        if not args:
            return self.say(chan, ("known terms: %s" % ','.join(map(unicode, self.bvars))).encode('utf-8'), conf.MAXLEN)
        al = args.split(None, 1)
        if len(al) == 1:  # display value
            if al[0] in self.bvars:
                self.say(chan, unicode(self.bvars[al[0]]).encode('utf-8'), conf.MAXLEN)
            else:
                self.say(chan, 'variable not found')
        else:
            try:
                if msg_cb:
                    t = eval(args, self.bvars)
                    if type(t[0]) == str and callable(t[1]):
                        self.bvars['msg_cb'][t[0]] = (re.compile(t[0], re.IGNORECASE), t[1])
                    else:
                        return self.say(chan, '\x034err\x03')
                else:
                    t = eval(al[1], self.bvars)
                    self.bvars[al[0]] = t
                    if assign_cmd:
                        if callable(t):
                            self.commands['!' + al[0]] = t
                        else:
                            return self.say(chan, '\x034 %s is not callable\x03' % str(type(t)))
                self.say(chan, '\x033ok\x03')
            except:
                self.say(chan, "\x02\x034%s" % repr(sys.exc_info()[1]))

    def signedOn(self):
        self.msg('nickserv', 'identify ' + conf.NICKSERV_PASS)
        self.join(self.factory.channel)
        #self.say(self.factory.channel, conf.BANNER)

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
        c, args = _tmp if len(_tmp) > 1 else (_tmp[0], None)
        if c in self.su_commands and user in self.authed_users:
            return self.su_commands[c](user, channel, args)
        elif c in self.commands:
            if time.time() - self.last_cmd > 2:
                self.last_cmd = time.time()
                return self.commands[c](user, channel, args)
        elif channel == self.nickname:
            al = args.split()
            if c == 'auth' and len(al) == 1:
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
            it = self.bvars['msg_cb'][k]
            if it[0].match(msg):
                return it[1](user, msg, it[0].findall(msg))


class IRCFactory(protocol.ReconnectingClientFactory):
    protocol = IRCBot

    def buildProtocol(self, address):
        p = self.protocol(self)
        self.connectedProto = p
        return p
