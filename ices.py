#!/usr/bin/env python
# -*- coding: utf-8 -*-
import xmlrpclib
def main():
    proxy = xmlrpclib.ServerProxy("http://localhost:8005/")
    print proxy.getNextTrack()
    return 0

if __name__ == '__main__':
	main()

