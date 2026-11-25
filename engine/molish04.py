from hashlib import sha256
from math import gcd
from finite03 import Engine, cbor, make_state

def pack(kind,body,v=4):return cbor(["Molish",0,v,kind,body])
def dg(x):return sha256(x).digest()

def parse(blob,kind,v=4):
    pos=0
    def dec(depth=0):
        nonlocal pos
        if depth>64 or pos>=len(blob):raise ValueError("PARSE")
        h=blob[pos];pos+=1;m=h>>5;a=h&31;n=a
        if a>=24:
            w={24:1,25:2,26:4}.get(a)
            if w is None or pos+w>len(blob):raise ValueError("PARSE")
            n=int.from_bytes(blob[pos:pos+w],"big");pos+=w
            if n < {1:24,2:256,4:65536}[w]:raise ValueError("NON_CANONICAL")
        if m==0:return n
        if m==4:return [dec(depth+1) for _ in range(n)]
        if m not in (2,3) or pos+n>len(blob):raise ValueError("PARSE")
        b=blob[pos:pos+n];pos+=n
        return b if m==2 else b.decode("utf-8")
    a=dec()
    if pos!=len(blob) or not isinstance(a, list) or len(a)!=5 or a[:4]!=["Molish",0,v,kind]:
        raise ValueError("ENVELOPE")
    return a[4]

def locked(key,level,ports=(),parts=(),version="1"):
    b=pack(3,["mol.test",key,version,level,list(ports),list(parts)])
    return ["mol.test",key,version,dg(b)],b

def assemble(blob,catalog,source_payloads=None):
    c,roots,expansions,sources,claims=parse(blob,0)
    core=parse(c,0,3)
    ent={e[0]:e[1] for e in core[0][0]}
    dom={v[0]:v[1]+1 for v in core[0][1]}
    slots={i:[mode,dom.get(d,0)] for i,e,n,d,mode in core[0][2]}
    counters={i:[u,m] for i,e,u,b,m in core[3]}
    ev={row[0] for row in core[0][3]}
    rels={x[0]:x[1] for x in core[2]}
    sorts={x[0]:set(x[1]) for x in core[1]}
    rules={r[1] for r in core[8]}|{r[0] for module in core[0][4] for r in module[5]}
    active={};owners=set();seen={}
    def resolve(lock,ancestors=()):
        n,k,v,h=lock
        if h in ancestors:raise ValueError("CYCLE")
        raw=catalog.get(h)
        if raw is None:raise ValueError("MISSING_DEFINITION")
        if dg(raw)!=h:raise ValueError("DEFINITION_DIGEST")
        d=parse(raw,3)
        if d[:3]!=[n,k,v] or not 0<=d[3]<=6:raise ValueError("DEFINITION_IDENTITY")
        identity=(n,k,v)
        if identity in seen and seen[identity]!=h:raise ValueError("LOCK_CONFLICT")
        seen[identity]=h
        if len({a[0] for a in d[4]})!=len(d[4]) or len({a[0] for a in d[5]})!=len(d[5]):raise ValueError("DEFINITION_DUPLICATE")
        return d
    def add(root,path,e,lock,bindings,ancestor):
        key=(root,path)
        if key in active or e in owners:raise ValueError("DUPLICATE_INSTANCE")
        if e not in ent:raise ValueError("ENTITY")
        d=resolve(lock,ancestor)
        if len(bindings)!=len(d[4]) or sorted(x[0] for x in bindings)!=sorted(x[0] for x in d[4]):raise ValueError("PORTS")
        by_port=dict(bindings)
        found=({i:[kind] for i,kind in ent.items()},slots,counters)
        for pid,kind,shape in d[4]:
            if found[kind].get(by_port[pid])!=shape:raise ValueError("PORT_TYPE")
        active[key]=(e,d,ancestor+(lock[3],))
        owners.add(e)
    for e,lock,bind in roots:add(e,(),e,lock,bind,())
    for root,raw_path,e,bind in expansions:
        path=tuple(raw_path)
        if not path or (root,path[:-1]) not in active:raise ValueError("PARENT_NOT_SELECTED")
        _,d,ancestor=active[root,path[:-1]]
        lock=dict(d[5]).get(path[-1])
        if lock is None:raise ValueError("PART")
        add(root,path,e,lock,bind,ancestor)
    origins={s[0]:s[1] for s in sources}
    if len(origins)!=len(sources):raise ValueError("SOURCE_ID")
    for source in sources:
        content=source[6]
        if content!=[0] and (len(content)!=2 or content[0]!=1 or len(content[1])!=32):raise ValueError("CONTENT_LOCK")
        if source_payloads is not None and source[0] in source_payloads and content!=[0] and dg(source_payloads[source[0]])!=content[1]:raise ValueError("SOURCE_DIGEST")
    if len({x[0] for x in claims})!=len(claims):raise ValueError("CLAIM_ID")
    for _,sid,eid,(kind,x,*rest),stance in claims:
        if sid not in origins or eid not in ev or stance not in (0,1,2) or kind not in (0,1,2):raise ValueError("CLAIM")
        if kind==0 and x not in ent or kind==1 and x not in rules:raise ValueError("CLAIM_TARGET")
        if kind==2 and (x not in rels or len(rest[0])!=len(rels[x]) or any(y not in sorts[z] for z,y in zip(rels[x],rest[0]))):raise ValueError("CLAIM_TARGET")
    return core,active,origins

def detail(active,root,path):
    try:return active[root,tuple(path)][0]
    except KeyError:raise ValueError("DETAIL_NOT_SELECTED") from None

def model04(core,roots=(),expanded=(),sources=(),claims=()):
    return pack(0,[pack(0,core,3),list(roots),list(expanded),list(sources),list(claims)])
def make_query(m,target,forbid=()):
    core=parse(m,0)[0]
    return pack(1,[dg(m),pack(1,[dg(core),0,target,list(forbid),[24,512,3000,4096]],3)])
def verify_query(m,q):
    mb,qb=parse(q,1);c=parse(m,0)[0]
    if mb!=dg(m) or parse(qb,1,3)[0]!=dg(c):raise ValueError("QUERY_BINDING")
    return parse(qb,1,3)

def make_result(m,q,start,events,target_binding=(),aggregate=0):
    nested=parse(q,1)[1]
    payload=[dg(parse(m,0)[0]),dg(nested),aggregate,int(aggregate==0),0 if aggregate==0 else 4,
             [[start,0,[events,list(target_binding)]]]]
    return pack(2,[dg(m),dg(q),pack(2,payload,3)])
def result_case(m, q, r, wanted):
    qq=verify_query(m,q)
    mb,qb,res=parse(r,2)
    parsed=parse(res,2,3)
    if mb!=dg(m) or qb!=dg(q) or parsed[0]!=qq[0] or parsed[1]!=dg(parse(q,1)[1]):
        raise ValueError("RESULT_BINDING")
    cases=[(a,b,c) for a,b,c in parsed[5] if dg(cbor(a))==wanted]
    if len(cases)!=1:
        raise ValueError("NO_WITNESS")
    return qq, parsed[2], cases[0]

def get_case(m,q,r,wanted):
    qq, verdict, (start, kind, proof) = result_case(m, q, r, wanted)
    if kind != 0:
        raise ValueError("NO_WITNESS")
    events, goalbind = proof
    eng=Engine(parse(parse(m,0)[0],0,3))
    s=make_state(start)
    if s not in eng.start:raise ValueError("INITIAL")
    states=[s]
    for rule,b,delta in events:
        nxt=eng.step(s,rule,b,qq[3])
        if nxt is None or nxt[1]!=delta:raise ValueError("TRACE")
        s=nxt[0];states.append(s)
    if tuple(goalbind) not in eng.domain_bindings(qq[2][0]) or not eng.guards(s,qq[2][1],goalbind):
        raise ValueError("GOAL")
    return states,events,verdict

def verify_closure(model, query, result, case_id):
    query_body, _, (initial, kind, proof) = result_case(model, query, result, case_id)
    if kind != 1:
        raise ValueError("NO_CLOSURE")
    engine = Engine(parse(parse(model, 0)[0], 0, 3))
    start = make_state(initial)
    states = [make_state(state) for state in proof]
    members = set(states)
    if start not in engine.start or start not in members or states != sorted(members):
        raise ValueError("CLOSURE_STATES")
    binders, conditions = query_body[2]
    for state in states:
        if not engine.valid(state):
            raise ValueError("CLOSURE_STATES")
        if any(engine.guards(state, conditions, binding) for binding in engine.domain_bindings(binders)):
            raise ValueError("CLOSURE_TARGET")
        if any(successor not in members for successor, _ in engine.edges(state, query_body[3])):
            raise ValueError("CLOSURE_EDGE")
    return states

def claim_ids(blob,initial):
    c,_,_,_,claims=parse(blob,0)
    core=parse(c,0,3)
    si={z[0]:i for i,z in enumerate(core[0][2])}
    scope={x[0]:x[4] for x in core[0][3]}
    return [cid for cid,_,eid,_,_ in claims if all(initial[0][si[s]]==v for _,s,v in scope[eid])]
def submit(m,ai,catalog):
    base,source,new=parse(ai,7)
    if base!=dg(m):raise ValueError("BASE_BINDING")
    _,_,sources=assemble(new,catalog)
    if sources.get(source)!=2:raise ValueError("AI_ORIGIN")
    return dg(new)

def verify_view(m,q,result,view):
    md,qd,rd,case,assets,schedule=parse(view,4)
    if [md,qd,rd]!=list(map(dg,[m,q,result])):raise ValueError("VIEW_BINDING")
    states,events,status=get_case(m,q,result,case)
    entity_ids={x[0] for x in parse(parse(m,0)[0],0,3)[0][0]}
    if len({a[0] for a in assets})!=len(assets) or any(a[1] not in entity_ids or len(a[2])!=32 for a in assets):
        raise ValueError("VIEW_ASSET")
    if schedule!=[0] and (len(schedule)!=2 or schedule[0]!=1):raise ValueError("SCHEDULE")
    steps=schedule[1] if schedule[0]==1 else []
    if any(not 0<=i<len(states) for i,_ in steps) or any(i>=j or t>u for (i,t),(j,u) in zip(steps,steps[1:])):
        raise ValueError("SCHEDULE")
    return states,status

def snapshot(m,q,r,case,step):
    states,_,_=get_case(m,q,r,case)
    if not 0<=step<len(states):raise ValueError("STEP")
    c=parse(parse(m,0)[0],0,3)
    return pack(5,[dg(m),dg(q),dg(r),case,step,c[6],states[step],claim_ids(m,states[0])])

def project(fine,fq,fr,coarse,cq,cert):
    fb,cb,(slots,counters,facts),mapping=parse(cert,6)
    if fb[:3]!=list(map(dg,[fine,fq,fr])) or cb!=list(map(dg,[coarse,cq])):raise ValueError("PROJECTION_BINDING")
    fs,events,_=get_case(fine,fq,fr,fb[3])
    fe=Engine(parse(parse(fine,0)[0],0,3))
    ce=Engine(parse(parse(coarse,0)[0],0,3))
    qt=verify_query(coarse,cq)
    cs={x[0]:i for i,x in enumerate(ce.m[0][2])}
    ss={x[0]:i for i,x in enumerate(fe.m[0][2])}
    if [i for i,_ in slots]!=list(cs) or [i for i,_ in counters]!=list(ce.counter_id):raise ValueError("INCOMPLETE_MAP")
    cd={x[0]:(x[1],tuple(x[2])) for x in ce.m[0][1]}|{0:(0,(0,1))}
    fd={x[0]:(x[1],tuple(x[2])) for x in fe.m[0][1]}|{0:(0,(0,1))}
    for sid,fid in slots:
        if fid not in ss or cd[ce.m[0][2][cs[sid]][3]]!=fd[fe.m[0][2][ss[fid]][3]]:raise ValueError("MAP_TYPE")
    for sid,fid in counters:
        if fid not in fe.count or ce.count[sid][0]!=fe.count[fid][0]:raise ValueError("MAP_TYPE")
    fmp=[((a[0],tuple(a[1])),(b[0],tuple(b[1]))) for a,b in facts]
    if len({a for a,b in fmp})!=len(fmp) or len({b for a,b in fmp})!=len(fmp):raise ValueError("MAP_DUPLICATE")
    if any(a[0] not in fe.rels or b[0] not in ce.rels or fe.rels[a[0]][1]!=1 or ce.rels[b[0]][1]!=1 or not fe.typed(*a) or not ce.typed(*b) for a,b in fmp):raise ValueError("MAP_FACT_TYPE")
    def p(s):
        y=(tuple(s[0][ss[x]] for _,x in slots),
           tuple(sorted(b for a,b in fmp if a in s[1])),
           tuple(s[2][fe.counter_id[x]] for _,x in counters))
        if not ce.valid(y):raise ValueError("MAP_STATE")
        return y
    c=p(fs[0])
    if c not in ce.start:raise ValueError("COARSE_INITIAL")
    out=[]
    actions={(r,tuple(b)):act for r,b,act in mapping}
    if len(actions)!=len(mapping):raise ValueError("DUPLICATE_MAP_EVENT")
    for i,(r,b,_) in enumerate(events):
        t=p(fs[i+1])
        if (r,tuple(b)) not in actions:raise ValueError("UNMAPPED_EVENT")
        act=actions[r,tuple(b)]
        if act==[0]:
            if c!=t:raise ValueError("HIDDEN_CHANGE")
            continue
        _,r0,b0=act
        nxt=ce.step(c,r0,b0,qt[3])
        if nxt is None or nxt[0]!=t:raise ValueError("COARSE_STEP")
        c=t;out.append([r0,b0,nxt[1]])
    b=next((b for b in ce.domain_bindings(qt[2][0]) if ce.guards(c,qt[2][1],b)),None)
    if b is None:raise ValueError("COARSE_GOAL")
    return c,out,b

def eligibility(m,request):
    md,adapter,time,species,events=parse(request,8)
    if md!=dg(m):raise ValueError("ADAPTER_BINDING")
    if adapter not in (0,1) or not species or not events:raise ValueError("ADAPTER_RECORD")
    base=parse(parse(m,0)[0],0,3)
    kinds={z[0]:z[1] for z in base[0][0]}
    eng=Engine(base)
    measures={};errors=set()
    for sid,entity,comp,unit,a in species:
        if sid in measures or entity not in kinds or kinds.get(comp)!=1:raise ValueError("SPECIES")
        measures[sid]=unit
        if a==[0]:errors.add(1)
        elif len(a)!=3 or a[0]!=1 or a[2]==0 or gcd(a[1],a[2])!=1:raise ValueError("AMOUNT")
    for rule,b,stoich,law,guard in events:
        if rule not in eng.rules or tuple(b) not in eng.domain_bindings(eng.rules[rule][0]):raise ValueError("EVENT")
        units=set()
        for sid,di,count in stoich:
            if sid not in measures or di not in (0,1) or count<=0:raise ValueError("STOICH")
            units.add(measures[sid])
        if law==[0]:errors.add(0)
        elif len(law)!=4 or law[0]!=1 or len(law[3])!=32:raise ValueError("LAW")
        elif units!={law[1]} or law[2]!=time:errors.add(2)
        if guard==1:errors.add(3)
        elif guard!=0:raise ValueError("GUARD")
    return pack(9,[dg(m),dg(request),int(not errors),sorted(errors)])
