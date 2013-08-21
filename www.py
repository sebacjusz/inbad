#!/usr/bin/env python
# -*- coding: utf-8 -*-
import cyclone.web
import json
import inba_cfg as conf


class WebInterface(cyclone.web.Application):
    def __init__(self, svc):
        self.svc = svc
        handlers = [
                (r'/loadbalancer.m3u', LBHandler),
                (r'/listeners.jsonp', ListenersHandler),
                (r'/vi_data.jsonp', ViHandler) ]
        settings = dict(debug=False)
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

class ViHandler(cyclone.web.RequestHandler):
    def get(self):
        if not self.application.svc.meta:
            return
        d = {'listeners' : self.application.svc.getListenerCount('total'),
                'listen_ogg' : self.application.svc.getListenURL('/vorbis-html5.ogg'),
                'listen_mp3' : self.application.svc.getListenURL('/mp3-mq.mp3'),
                'np' : {k:v for k,v in self.application.svc.meta.iteritems() if k in conf.safe_params}}
        self.set_header("Content-Type", "text/javascript")
        return self.write('radio_status_reply('+json.dumps(d)+')')
