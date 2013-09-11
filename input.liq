# vim: set filetype=ocaml:

%include "jsonrpc.liq"
%include "config.liq"

dj_connections = ref 0
rec_start_fun = ref fun()->ignore(0)
rec_stop_fun = ref fun()->ignore(0)

override_input = input.harbor("master_override", password=override_pass, port=8001, max=15.,
    on_connect=fun(_)-> ignore(inbad.call("override_connected")),
    on_disconnect=fun() -> ignore(inbad.call("override_connected")))

def _new_connection(meta)=
    print(meta)
    dj_connections := !dj_connections + 1
    if !dj_connections == 1 then
        f = !rec_start_fun
        ignore(f())
    end
    inbad.dj_connected(meta)
end
def _disconnect()=
    dj_connections := !dj_connections - 1
    if !dj_connections < 1 then
        f = !rec_stop_fun
        ignore(f())
    end
    print(!dj_connections)
    inbad.dj_disconnected()
end

def register_rec_stop(f)=
    rec_stop_fun := f
end
def register_rec_start(f)=
    rec_start_fun := f
end

def create_request(id)=
    s = request.equeue(id=id)
    mixer.add(id, s)
    "ok"
end

def create_input(id)=
    auth_fun = fun(u,p)-> if u == "source" then inbad.auth_dj(id, p) else false end
    s = input.harbor(id, port=8001, max=5., auth=auth_fun,
        on_connect=_new_connection,
        on_disconnect=_disconnect)
    mixer.add(id, s)
    "ok"
end

def add_http_remote(q)=
    qq = string.split(separator="\|", q)
    id = list.nth(qq, 0)
    url = list.nth(qq, 1)
    s = input.http(id=id, url)
    mixer.add(id, s)
    "ok"
end

server.register("create_request", create_request)
server.register("create_input", create_input)
server.register("add_http_remote", add_http_remote)
