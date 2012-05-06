#!/usr/bin/env python
# -*- coding: utf-8 -*-
import datetime, time

class MetaFormatter(object):
    def __init__(self, s):
        self.svc = s
    PLAIN, IRC = range(2)
    TIME_ABS, TIME_REL = range(2)

    def __call__(self, fmt=PLAIN, time_fmt=None, track=True, s_name=False, s_desc=False, notify_offline=False):
        m = self.svc.meta
        if not m:
            if notify_offline:
                return u"nie ma inby, kłapołech zjat."
            return
        if time_fmt == self.TIME_ABS:
            p_time = time.strftime("%H:%M") + '\t'
        elif time_fmt == self.TIME_REL:
            p_time = str(datetime.timedelta(seconds=int(time.time() - self.rec_start))) + '\t'
        else:
            p_time = ""
        _f = lambda x: m[x] if m.get(x, None) else u''
        p_name = u"{name_b}%s{name_e}" % _f('server_name') if s_name else u''
        p_desc = u"{desc_b}%s{desc_e}" % _f('server_description') if s_desc else u''
        p_track = u"{track_b}%s{track_sep}%s{track_e}" % (_f('artist'), _f('title')) if track else u''
        out = p_time + p_name + p_desc + p_track
        if fmt == self.PLAIN:
            return out.format(name_b='****** ', desc_b='(', desc_e=')', track_sep=' - ',
                    name_e='', track_b='', track_e='')
        elif fmt == self.IRC:
            return out.format(name_b='\x02\x034', name_e='\x03\x02',
                    desc_b='(\x039', desc_e='\x03)', track_b=u' właśnie nakurwia: \x02',
                    track_sep='\x02 - ', track_e='')
        else:
            raise Exception('wrong format')
