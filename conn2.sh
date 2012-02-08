#!/bin/bash
#echo `id` >>/anon/tlog
#echo `pwd` >>/anon/tlog
chmod 666 /anon/rcp/tmp_rec.ogg
#echo end >>/anon/tlog
/anon/rcp/icecast-connect.py
