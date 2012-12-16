# vim: set filetype=ocaml:

%include "jsonrpc.liq"
%include "config.liq"

override_input = input.harbor("master_override", password=override_pass, port=8001, max=15.,
    on_connect=fun(_)-> ignore(inbad.call("override_connected")),
    on_disconnect=fun() -> ignore(inbad.call("override_connected")))

dj_input = input.harbor("dj", port=8001, max=5., auth=inbad.auth_dj,
    on_connect=inbad.dj_connected,
    on_disconnect=inbad.dj_disconnected)

request_enable = ref false

def new_request()=
    log("loading new request")
    resp = "" #inbad.call("new_request")
    log(resp)
    if string.length(resp) > 10000 then
        uri = snd(list.nth(string.extract(pattern="^\"(.+)\"$", resp),0))
        request.create(uri)
    else request.create("/mnt/soft/M/Pryda/37. Pryda - Mirage.mp3") end
end

server.register("request_enable", fun(a) -> begin
    request_enable := (if a == "true" then true else false end) "ok" end)

request_input = at({!request_enable}, request.dynamic(new_request))
