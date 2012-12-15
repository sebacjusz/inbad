#!/usr/bin/env liquidsoap
# vim: set filetype=ocaml:

def _jsonify (_fun_name, ~args=[] )
    params = json_of(args)
    m = "{\"method\":\"" ^ _fun_name ^"\", \"params\": "
    m ^ params ^ "}"
end

def jsonrpc.call(server, _fun, ~arg=[])=
    data = _jsonify(_fun, args=arg)
    resp = http.post(data=data, server)
    d = snd(resp)
    snd(list.nth(string.extract(pattern="^\[(.+)\]$",d),0))
end

inbad.call = jsonrpc.call("http://localhost:8005/")

inbad.dj_connected = fun(_) -> ignore(inbad.call("server_sourceConnected"))
inbad.dj_disconnected = fun() -> ignore(inbad.call("server_sourceDisconnected"))
inbad.rec_stopped = fun(file) -> ignore(inbad.call("server_recStopped",
    arg=[file]))

def inbad.auth_dj(user,pass) =
    resp = inbad.call("authdj", arg=[user,pass])
    if resp == "true" then true else false end
end
