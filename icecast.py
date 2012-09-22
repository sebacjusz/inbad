#!/usr/bin/env python
# -*- coding: utf-8 -*-

from lxml import etree
from twisted.web import client
client.HTTPClientFactory.noisy = False      # get rid of that 'starting factory' log flood
from twisted.application import service
from twisted.internet import reactor, task
import json, time
from collections import namedtuple, defaultdict

ServerAuth = namedtuple('ServerAuth', 'user passwd')
Mountpoint = namedtuple('Mountpoint', 'master relays')
watch_keys = ('artist', 'title', 'server_description', 'server_name')


def _stderrback(e):
    e.printBriefTraceback()


def getStats(server, auth):
    basicAuth = ('%s:%s' % auth).encode('base64')
    authHeader = "Basic " + basicAuth.strip()
    d = client.getPage('http://' + server + '/admin/stats', headers={"Authorization": authHeader})
    d.addCallback(lambda x: etree.fromstring(x))
    def convert(d):
        for k in d:
            if not d[k]:
                del d[k]
            if k in ('artist', 'title', 'server_description', 'server_name', 'file'):
                if type(d[k]) == unicode:
                    continue
                try:
                    d[k] = d[k].decode('utf-8')
                except UnicodeEncodeError:
                    d[k] = d[k].decode('cp1250')
            elif k in ('listeners', 'listener_peak'):
                d[k] = int(d.get(k, 0))
        return d
    def parse_data(tree):
        d={}
        for i in tree.iter('source'):
            i_d = defaultdict(unicode)
            for j in i:
                i_d[j.tag] = j.text
            d[i.attrib['mount']] = convert(i_d)
        return d
        #return dict([(i.attrib['mount'],
        #    convert(dict([(j.tag, j.text) for j in i]))) for i in tree.iter('source')])
    return d.addCallback(parse_data)


class IcecastPoller(service.Service, dict):
    """IcecastPoller(mountpoints, servers, interval=2)
       mountpoints = { '<mount>' : ( '<master server>', { '<relay>' : '<relay mount>' } ) }
       servers = { '<host>:<port>' : ( '<admin user>', '<admin password>' ) }
       master_in_relays - when True, master mountpoint will be added to relay list
       Servers will be polled every <interval> seconds.
       Relays which haven't been up for more than <timeout> seconds won't be counted.
       TODO: Use persistent connections"""
    def __init__(self, mountpoints, servers, interval=4, master_in_relays=True, timeout=10):
        self.loglevel = 2
        self._interval = interval
        self.timeout = timeout
        self.master_in_relays = master_in_relays
        self.server_data = {}
        self.mounts = dict((k, Mountpoint._make(mountpoints[k])) for k in mountpoints)
        self.servers = dict((k, ServerAuth._make(servers[k])) for k in servers)
        super(IcecastPoller, self).__init__()

    def log(self, msg, level=0):
        if level >= self.loglevel:
            print msg

    def startService(self):
        self._slc = task.LoopingCall(self.updateServers)
        self._mlc = task.LoopingCall(self.updateMounts)
        self._slc.start(self._interval, now=False)
        self._mlc.start(self._interval / 2, now=False)
        service.Service.startService(self)

    def updateServers(self):
        for s in self.servers:
            def _set(v, srv):
                self.log('updated %s' % srv, 0)
                self.server_data[srv] = v
                self.server_data[srv]['_last_update'] = int(time.time())
            d = getStats(s, self.servers[s])
            d.addCallback(_set, srv=s)
            d.addErrback(_stderrback)

    def updateMounts(self):
        for m,m_d in self.mounts.iteritems():
            if m_d.master not in self.server_data or m not in self.server_data[m_d.master]:
                new = None  # mountpoint is offline, so skip it
                continue
            new = self.server_data[m_d.master][m]
            new['relays'] = {}

            for i in m_d.relays:
                if i not in self.server_data:
                    continue    # relay is offline
                i_data = self.server_data[i]
                i_mount = m_d.relays[i]
                if i_mount not in i_data:
                    continue
                if i_data['_last_update'] + self.timeout < time.time():
                    del new['relays'][i]    # don't count relays that went down
                else:
                    new['relays'][i] = i_data[i_mount]['listeners']

            if self.master_in_relays:
                new['relays'][self.mounts[m].master] = new['listeners'] - len(new['relays'])
            filt = lambda d: {k: d[k] for k in d if k in watch_keys}
            if filt(self.get(m, dict())) != filt(new):
                self[m] = new
                self.parent.event_pub('metadata_changed')
                self.log('meta for %s changed: %s' %(m, filt(new)), 1)
            else:   # yeah, that is pretty dumb.
                self[m] = new
            self.log('relays for %s:' % m + repr(new['relays']), 1)
