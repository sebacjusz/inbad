#!/usr/bin/env liquidsoap
# vim: set filetype=ocaml:
%include "jsonrpc.liq"
%include "config.liq"
szperdo_on = ref false
auto_nrj = ref false
rec_source = ref source

set("server.timeout",-1.)

trans = fun(a, b) -> add([fade.initial(b), fade.final(a)])
server.register("szperdo.start", fun (_) -> begin szperdo_on := true "ok" end)
server.register("szperdo.stop", fun(_) -> begin szperdo_on := false "ok" end)
server.register("nrj.off", fun(_) -> begin auto_nrj := false "ok" end)
server.register("nrj.on", fun(_) -> begin auto_nrj := true "ok" end)
server.register("jcall", fun(arg) -> json_of(inbad.call(arg)))

szperdo_i = input.http(id="szperdo", "http://localhost:8000/szperdo.ogg")
szperdo_sw = switch(track_sensitive=false, [({!szperdo_on}, szperdo_i)])

jng_pls = playlist.safe("jng.pls", mime_type="audio/mpegurl", mode="random")
idle_r = random(weights=[1, 10], [jng_pls, standby_loop])

live_i = input.harbor("dj_live_in", password=override_pass, port=8001, max=15.,
    on_connect=fun(_)-> ignore(inbad.dj_connected()),
    on_disconnect=fun() -> ignore(inbad.dj_disconnected()))

switched = fallback(track_sensitive=false, transitions=[trans, trans, trans],
    [live_i, szperdo_sw, idle_r])

p_sos=switched
sos = switch(track_sensitive=false, [ ({!auto_nrj}, nrj(p_sos)),
    ({true},p_sos)])

final_output = sos

std_icecast(%vorbis(samplerate=44100, channels=2, quality=0.4),
    mount = "vorbis-hq.ogg", final_output)
std_icecast(%vorbis(samplerate=44100, channels=2, quality=0.2),
    mount = "vorbis-lq.ogg", final_output)
std_icecast(%mp3.abr(min_bitrate=64, bitrate=96, max_bitrate=128),
    mount = "mp3-abr-lq.mp3", final_output)
std_icecast(%mp3.abr(min_bitrate=128, bitrate=192, max_bitrate=256),
    mount = "mp3-abr-hq.mp3", final_output)

def start_rec() = 
    source.shutdown(rec_source)
    rec_source := output.file(%vorbis(samplerate=44100, channels=2,
        quality=0.4), on_close=inbad.rec_stopped,
        rec_path+"%Y/%m-%d/%H:%M:%S(live).ogg")
    log("start_rec")
end
