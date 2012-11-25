#!/usr/bin/env liquidsoap
# vim: set filetype=ocaml:

def _jsonify (_fun_name, ~args=[] )
    params = json_of(args)
    m = "{\"method\":\"" ^ _fun_name ^"\", \"params\": "
    m ^ params ^ "}"
end

def jsonrpc.call(server, _fun, ~argd=[], ~argl)=
    arg = if list.length(argd)>0 then [argd] else argl end
    data = _jsonify(_fun, args=arg)
    http.post(data=data, server)
end

inbad.call = jsonrpc.call("http://localhost:8005/")

inbad.dj_connected = fun() -> inbad.call("server_sourceConnected")
inbad.dj_disconnected = fun() -> inbad.call("server_sourceDisconnected")
inbad.rec_stopped = fun(file) -> ignore(inbad.call("server_recStopped",
    argl=[file, ""]))
