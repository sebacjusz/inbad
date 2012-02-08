#!/usr/bin/env python
# -*- coding: utf-8 -*-
import xmlrpclib, os
def main():
    proxy = xmlrpclib.ServerProxy("http://localhost:8005/")
    proxy.server_sourceConnected()
    return 0

if __name__ == '__main__':
	main()

