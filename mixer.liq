#!/usr/bin/env liquidsoap
# vim: set filetype=ocaml:

def assoc_any(k, l, default)=
    f = fun(prev,i)-> if fst(i)==k then snd(i) else prev end
    list.fold(f, default, l)
end

input_list = ref []

def mixer.output()=
    def amp(s)=
        p = snd(s)
        n = fst(s)
        f = fun()-> snd(assoc_any(n, !input_list, (blank(),0.0)))
        amplify(f, fst(p))
    end
    sources = list.map(amp, !input_list)
    add(sources)
end

def mixer.add(k,s,~vol=0.0)=
    input_list := list.append([(k,(s,vol))], !input_list)
end

def mixer.getdata()=
    f = fun(i) -> (fst(i), snd(snd(i)))
    list.map(f, !input_list)
end

server.register("mixer.getdata", fun(_)-> json_of(mixer.getdata()))

def mixer.set(k, v)=
    def f(i)=
        if fst(i)==k then
            (k, (fst(snd(i)), v))
        else
            i
        end
    end
    input_list := list.map(f, !input_list)
end

def _set_helper(arg)=
    a = string.split(separator=":", arg)
    v = float_of_string(list.nth(a,1))
    mixer.set(list.hd(a), v)
    "ok"
end
server.register("mixer.set", _set_helper)
