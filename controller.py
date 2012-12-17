# -*- coding: utf-8 -*-
from twisted.internet import protocol, defer
from twisted.protocols.basic import NetstringReceiver
import json

class Error(Exception):
    def __init__(self, error, d=None):
        if d:
            self.data=d
            assert(type(d)==dict)
        else:
            self.data={}
        self.data['error'] = error

class ControllerProtocol(NetstringReceiver):
    def __init__(self, service):
        self._authenticated=False
        self.service = service
        pass

    def _error(self, fail):
        print 'FAIL:', fail
        v = fail.value
        if not isinstance(v, Error):
            v = Error(type(v).__name__, {'exception':v.message})
        return v.data

    def _respond(self, d, rid):
        print 'resp', type(d), repr(d)
        if d is None:
            d = {}
        d['id'] = rid
        d['type'] = 'response'
        d['success'] = False if d.get('error') else True
        return self.sendString(json.dumps(d))

    def stringReceived(self, string):
        print 'recv', string
        try:
            data = json.loads(string)
            cmd = data['cmd']
        except (ValueError,KeyError):
            return self.sendString('{"error":"invalid_request"}')
        try:
            rid = int(data['id'])
        except (ValueError,KeyError):
            rid = None
        if not self._authenticated and cmd != 'login':
            d = defer.fail(Error('not_logged_in'))
        else:
            try:
                f = getattr(self, 'cmd_'+cmd)
                if not callable(f):
                    raise AttributeError
                d = defer.maybeDeferred(f, data)
            except AttributeError:
                d = defer.fail(Error('invalid_command'))
        d.addErrback(self._error)
        return d.addCallback(self._respond, rid)

    def cmd_login(self, data):
        try:
            user = data['user']
            pwd = data['pass']
        except KeyError:
            raise Error('invalid_request')
        if self.service.auth(user,pwd):
            self._authenticated = True
        else:
            raise Error('invalid_password')
    
    def cmd_getMixer(self, data):
        return self.service.lsf.instance.getMixer()
    def cmd_setMixer(self, data):
        try:
            k = d['channel']
            v = float(d['value'])
        except (ValueError,KeyError):
            raise Error('invalid_request')
        def _cb(d):
            if d=='ok':
                return self.service.lsf.instance.getMixer()
            else:
                raise Error('liquidsoap', {'liq_err': d})
        return self.service.lsf.instance.setMixer(k, v).addCallback(_cb)


class ControllerFactory(protocol.ServerFactory):
    protocol = ControllerProtocol
    def __init__(self, service):
        self.service = service

    def buildProtocol(self, addr):
        p = self.protocol(self.service)
        p.factory = self
        return p
