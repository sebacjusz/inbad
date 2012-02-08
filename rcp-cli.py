#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os, sys, xmlrpclib
rpr = xmlrpclib.ServerProxy("http://localhost:8005/")

cmd=sys.argv[1]

if cmd == 'list':
    print '\n'.join(rpr.q_list())
elif cmd == 'sage':
    rpr.q_skip()
elif cmd == 'np':
    print str(''.join(rpr.q_np()))
elif cmd == 'add':
    rpr.q_add( sys.argv[2:] )
