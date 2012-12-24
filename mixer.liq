#!/usr/bin/env liquidsoap
# vim: set filetype=ocaml:

def assoc_any(k, l, default)=
    f = fun(prev,i)-> if fst(i)==k then snd(i) else prev end
    list.fold(f, default, l)
end

input_list = ref []
output_source = ref noise()
meta_master = ref ""
_def = (blank(),(0.0,[]))
_insert_meta = ref fun(m)->ignore(0)

def mixer.create_source()=
    def amp(s)=
        p = snd(s)
        n = fst(s)
        f = fun()-> fst(snd(assoc_any(n, !input_list, _def)))
        amplify(f, fst(p))
    end
    m_s = fst(assoc_any(!meta_master, !input_list, (assoc_any("idle", !input_list, _def))))
    sources = list.map(amp, !input_list)
    op = insert_metadata(add(sources))
    _insert_meta := fst(op)
    ignore(on_metadata(fst(op), m_s))
    snd(op)
end

def mixer.output()=
    source.dynamic({[!output_source]})
end

def mixer.rebuild()=
    old = !output_source
    output_source := mixer.create_source()
    source.shutdown(old)
end

server.register("mixer.rebuild", fun(_)->begin mixer.rebuild() "ok" end)

def mixer.set_master(k)=
    meta_master := k
    _f = !_insert_meta
    _f(snd(snd(assoc_any(!meta_master, !input_list, _def))))
    "ok"
end
server.register("mixer.set_master", mixer.set_master)

def mixer.set_meta(k, v)=
    def f(i)=
        if fst(i)==k then
            (k, (fst(snd(i)), (fst(snd(snd(i))), v)))
        else
            i
        end
    end
    input_list := list.map(f, !input_list)
end
def mixer.add(k,s,~vol=0.0)=
    _s = on_metadata(fun(m)->mixer.set_meta(k,m), s)
    input_list := list.append([(k,(_s,(vol, [])))], !input_list)
end

def mixer.remove(key, ~destroy=true) = 
  def parse_list(ret, current_element) = 
    # ret is of the form: (matching_sources, remaining_sources)
    matching_sources = fst(ret)
    remaining_sources = snd(ret)

    k = fst(current_element)
    if k == key then
      (list.append( [snd(current_element)], 
                     matching_sources),
       remaining_sources)
    else
      (matching_sources,
       list.append([current_element], 
                    remaining_sources))
    end
  end
    
  result = list.fold(parse_list, ([], []), !input_list)
  matching_sources = fst(result)
  remaining_sources = snd(result)

  input_list := remaining_sources

  if list.length(matching_sources) == 0 then
      log("(mixer.remove)FAIL: id not found")
  else
    if destroy then
        list.iter(fun(i)->source.shutdown(fst(i)), matching_sources)
        mixer.rebuild()
    end
  end
end

server.register("mixer.remove", fun(k)->begin mixer.remove(k) "ok" end)

def mixer.getdata()=
    f = fun(i) -> (fst(i), fst(snd(snd(i))))
    list.map(f, !input_list)
end

server.register("mixer.getdata", fun(_)-> json_of(mixer.getdata()))

def mixer.set(k, v)=
    def f(i)=
        if fst(i)==k then
            (k, (fst(snd(i)), (v, snd(snd(snd(i))))))
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
