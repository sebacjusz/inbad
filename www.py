#!/usr/bin/env python
# -*- coding: utf-8 -*-
import cyclone.web
import json


class WebInterface(cyclone.web.Application):
    def __init__(self, svc):
        self.svc = svc
        handlers = [
                (r'/loadbalancer.m3u', LBHandler),
                (r'/listeners.jsonp', ListenersHandler) ]
        settings = dict(debug=True)
        cyclone.web.Application.__init__(self,handlers,**settings)

class LBHandler(cyclone.web.RequestHandler):
    def get(self):
        m = self.get_argument('m')
        self.set_header("Content-Type", "audio/mpegurl")
        return self.write(self.application.svc.getListenURL('/'+m))

class ListenersHandler(cyclone.web.RequestHandler):
    def get(self):
        t = self.get_argument('t', default='all')
        self.set_header("Content-Type", "text/javascript")
        d = json.dumps(self.application.svc.getListenerCount(t))
        return self.write('radioreply('+d+')')
