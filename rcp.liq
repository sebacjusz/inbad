#!/usr/bin/env liquidsoap
# vim: set filetype=ocaml:
%include "jsonrpc.liq"
%include "config.liq"
%include "mixer.liq"
%include "input.liq"

auto_nrj = ref false
rec_source = ref output.dummy(blank())

set("server.timeout",-1.)

trans = fun(a, b) -> add([fade.initial(b), fade.final(a)])
server.register("nrj.off", fun(_) -> begin auto_nrj := false "ok" end)
server.register("nrj.on", fun(_) -> begin auto_nrj := true "ok" end)
server.register("jcall", fun(arg) -> json_of(inbad.call(arg)))
server.register("eval", eval)

def new_metadata(d)
    def ret1()
        ignore(inbad.calld("new_track", [d]))
        (-1.0)
    end
    ignore(add_timeout(fast=false, 0.01, ret1))
end

jng_pls = playlist.safe("jng.pls", mime_type="audio/mpegurl", mode="random")
idle = random(weights=[1, 10], [jng_pls, standby_loop])
idle_r = rewrite_metadata(update=false, strip=true, [("_idle", "true")], idle)

dj_input = create_input("dj")
ignore(dj_input)
mixer.set("dj", 1.0)

#calling rebuild before any sources are running causes an exception
add_timeout(0.5,fun()->begin mixer.rebuild() (-1.0) end)
sos = fallback(track_sensitive=false, [override_input, mixer.output(),idle_r])

final_output = on_metadata(new_metadata, server.rms(id="final_output",sos))

std_icecast(%vorbis(samplerate=44100, channels=2, quality=0.6),
    mount = "vorbis-hq.ogg", final_output)
#std_icecast(%vorbis(samplerate=44100, channels=2, quality=0.2),
#    mount = "vorbis-lq.ogg", final_output)
std_icecast(%mp3.abr(min_bitrate=48, bitrate=64, max_bitrate=96),
    mount = "mp3-lq.mp3", final_output)
std_icecast(%mp3.abr(min_bitrate=128, bitrate=160, max_bitrate=192),
    mount = "mp3-mq.mp3", final_output)

std_icecast(%vorbis(samplerate=44100, channels=2, quality=0.5),
    mount = "vorbis-html5.ogg", drop_metadata(final_output))

#monitor
output.harbor(auth=inbad.auth_dj, mount="/monitor-flac.ogg", port=8001,
    %ogg(%flac(compression=7, bits_per_sample=16)), final_output)

def start_rec() 
    rec_source := output.file(on_close=inbad.rec_stopped,
        %vorbis(samplerate=44100, channels=2,
        quality=0.6), rec_path^"%Y/%m-%d/%H:%M:%S(live).ogg", final_output)
    log("start_rec")
end
register_rec_start(start_rec)
register_rec_stop(fun()->source.shutdown(!rec_source))
