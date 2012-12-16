#!/usr/bin/env liquidsoap
# vim: set filetype=ocaml:

def _jsonify (_fun_name, args)
    params = json_of(args)
    m = "{\"method\":\"" ^ _fun_name ^"\", \"params\": "
    m ^ params ^ "}"
end

def jsonrpc._call(server, data)=
    resp = http.post(data=data, server)
    d = snd(resp)
    m = string.extract(pattern="^\[(.+)\]$",d)
    if list.length(m) < 1 then ""
    else snd(list.nth(m,0)) end
end

jsonrpc.call = fun(s,f,~arg=[])->jsonrpc._call(s,_jsonify(f,arg))
jsonrpc.calld = fun(s,f,a)->jsonrpc._call(s,_jsonify(f,a))

inbad.call = jsonrpc.call("http://localhost:8005/")
inbad.calld = jsonrpc.calld("http://localhost:8005/")

inbad.dj_connected = fun(_) -> ignore(inbad.call("server_sourceConnected"))
inbad.dj_disconnected = fun() -> ignore(inbad.call("server_sourceDisconnected"))
inbad.rec_stopped = fun(file) -> ignore(inbad.call("server_recStopped",
    arg=[file]))

def inbad.auth_dj(user,pass) =
    resp = inbad.call("authdj", arg=[user,pass])
    if resp == "true" then true else false end
end
