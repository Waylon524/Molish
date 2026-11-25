"""Run the published Molish 0.3 conformance fixtures against the shared engine."""

from collections import deque
from hashlib import sha256
import json

from finite03 import C, V, Engine, adds, cbor, cmp, drops, eff, free, has, num, skel, template, wire

tested=[]
def ck(name,test):
    assert test,name
    tested.append(name)
def failed(fn,reason):
    try:fn()
    except ValueError as e:return str(e)==reason
    return False
def ids(result):return [ev[0] for ev in result[1]]

# Repair principle: two directed tracks, declared ranges, synthetic materials.
# Relations installed(range,fragment), lesion(site), vacant-reserve(fragment),
# gap(range,fragment), restored(range,fragment), allows(range,fragment), replaces(new,old).
rs=[[1,[2,4],1,[[0],[1]]],[2,[3],1,[]],[3,[4],1,[]],[4,[2,4],1,[[0]]],
    [5,[2,4],1,[[0],[1]]],[6,[2,4],0,[]],[7,[4,4],1,[[0]]]]
rsorts=[[1,[11,12]],[2,[21,22]],[3,[31,32,33,34,35,36,37,38,39]],[4,[51,52,53,54]]]
cut=template(100,[1,2,3,4],[[6,V(1),V(0)],[5,V(1),V(2)],has(1,V(1),V(3)),has(2,V(2))],
             [drops(1,V(1),V(3)),drops(2,V(2)),adds(4,V(1),V(3))])
patch=template(110,[2,4,4],[has(4,V(0),V(1)),has(3,V(2)),has(6,V(0),V(2)),[9,V(1),V(2)],free(1,0,V(0))],
               [drops(3,V(2)),drops(4,V(0),V(1)),adds(1,V(0),V(2)),adds(5,V(0),V(2)),adds(7,V(2),V(1))])
rm=skel([11,12,21,22,31,32,33,34,35,36,37,38,39,51,52,53,54],rsorts,rs,
        tracks=[[11,[31,32,33,34]],[12,[35,36,37,38,39]]],ranges=[[21,11,1,3],[22,12,2,5]],
        static=[[6,[21,52]],[6,[22,54]]],
        initial=[([[1,[21,51]],[2,[32]],[3,[52]],[3,[54]]],[]),
                 ([[1,[22,53]],[2,[37]],[3,[52]],[3,[54]]],[])],templates=[cut,patch])
e=Engine(rm)
for i,range_id,new,old in [(0,21,52,51),(1,22,54,53)]:
    out=e.explore(e.start[i],[[],[has(5,C(range_id),C(new))]])
    ck(f"repair same template on input {i+1}",ids(out)==[100,110] and e.trace(e.start[i],out[1])==out[0])
    ck(f"repair retained material identity {i+1}",(1,(range_id,new)) in out[0][1] and (1,(range_id,old)) not in out[0][1] and (7,(new,old)) in out[0][1])
s=e.start[0]
cross=(s[0],tuple(sorted(set(s[1])|{(2,(36,))})),s[2])
ck("wrong aligned strand despite marked damage at matched index",e.step(cross,100,(11,21,36,51)) is None)
ck("wrong explicit strand binding",e.step(e.start[0],100,(12,21,32,51)) is None)
ck("half-open endpoint does not match",not e.guards(e.start[0],[[5,C(21),C(34)]],()))
ck("no replacement without correct declared role",e.step(e.step(e.start[0],100,(11,21,32,51))[0],110,(21,51,54)) is None)
reused=rm.copy()
reused[6]=sorted(rm[6]+[[6,[22,52]]])
reused[7]=[1,[[[],[[1,[21,52]],[3,[54]],[4,[22,53]],[5,[21,52]],[7,[52,51]]],[]]]]
eu=Engine(reused)
ck("consumed replacement cannot be reused even if compatible",eu.step(eu.start[0],110,(22,53,52)) is None and eu.step(eu.start[0],110,(22,53,54)) is not None)
repaired=e.explore(e.start[0],[[],[has(5,C(21),C(52))]])
ck("forged replacement delta rejected",e.trace(e.start[0],[repaired[1][0],[110,[21,51,52],[]]]) is None)
bad=rm.copy();bad[5]=[[21,11,0,5]]
ck("outside range rejected at load",failed(lambda:Engine(bad),"range"))

# Mechanism of directional occupancy, not a kinetic model.
move=template(200,[1,2,3,3],[has(1,V(0),V(2)),[4,V(1),V(2),V(3)],free(1,1,V(3))],
              [drops(1,V(0),V(2)),adds(1,V(0),V(3))])
mm=skel([11,12,31,32,33,34,35,36,61,62],[[1,[61,62]],[2,[11,12]],[3,[31,32,33,34,35,36]]],
        [[1,[1,3],1,[[0],[1]]]],tracks=[[11,[31,32,33]],[12,[36,35,34]]],
        initial=[([[1,[61,31]]],[]),([[1,[62,36]]],[])],templates=[move])
e=Engine(mm)
for i,occupant,track,a,b in [(0,61,11,31,32),(1,62,12,36,35)]:
    out=e.explore(e.start[i],[[3],[has(1,C(occupant),V(0)),[4,C(track),C(a),V(0)]]])
    ck(f"one stepping template on track {i+1}",ids(out)==[200] and out[2]==[b] and e.trace(e.start[i],out[1])==out[0])
    ck(f"stepping exact released/acquired delta {i+1}",out[1][0][2]==[[1,1,[occupant,b]],[2,1,[occupant,a]]])
    ck(f"cannot reverse on track {i+1}",e.step(out[0],200,(occupant,track,b,a)) is None)
ck("no hop across declared tracks",e.step(e.start[0],200,(61,11,31,35)) is None)
occupied=mm.copy();occupied[7]=[1,[[[],[[1,[61,31]],[1,[62,32]]],[]]]]
eo=Engine(occupied)
ck("no transition to occupied target",eo.step(eo.start[0],200,(61,11,31,32)) is None)
duplicate=mm.copy();duplicate[7]=[1,[[[],[[1,[61,31]],[1,[62,31]]],[]]]]
ck("relation-key duplicate initial rejected",failed(lambda:Engine(duplicate),"initial"))
ck("grounded intervention",e.step(e.start[0],200,(61,11,31,32),[[3,200,[61,11,31,32]]]) is None)
ck("same rule ID can still act on other binding",e.step(e.start[1],200,(62,12,36,35),[[3,200,[61,11,31,32]]]) is not None)

# Credits are invented symbolic unit values. Two read-only costs bind the exact same rule set.
credit="credit"; molecule="molecule"
one=num(credit,1); one_m=num(molecule,1); cost=num(credit,terms=[[7,1]])
c_rules=[template(10,[],[],[eff(1,1,one),eff(2,0,one)]),
         template(20,[],[cmp(5,num(credit,terms=[[2,1]]),cost)],
                  [eff(2,1,cost),eff(3,1,one_m),eff(4,0,one_m),eff(6,0,cost)]),
         template(30,[],[],[eff(2,1,one),eff(5,0,one)])]
cm=skel([1],counter=[[1,1,credit,6,0],[2,1,credit,4,0],[3,1,molecule,2,0],
                      [4,1,molecule,2,0],[5,1,credit,6,0],[6,1,credit,6,0],[7,1,credit,3,1]],
        initial=[([],[4,0,2,0,0,0,2]),([],[6,0,2,0,0,0,3])],templates=c_rules)
e=Engine(cm)
product_goal=[[],[cmp(5,num(molecule,terms=[[4,1]]),one_m)]]
for i,start in enumerate(e.start):
    full=e.explore(start)
    win=e.explore(start,product_goal)
    k=start[2][6]
    total=start[2][0]
    ck(f"first coupling uses shared template, initial {i+1}",ids(win)==[10]*k+[20])
    ck(f"credit conservation initial {i+1}",all(s[2][0]+s[2][1]+s[2][4]+s[2][5]==total for s in full))
    ck(f"coupled charge and material accounting initial {i+1}",all(s[2][2]+s[2][3]==2 and s[2][5]==k*s[2][3] for s in full))
    ck(f"blocking coupling proves no product, initial {i+1}",e.explore(start,product_goal,[[0,20]]) is None)
cm_limit=cm.copy();cm_limit[3]=[x[:] for x in cm[3]];cm_limit[3][3][3]=1
el=Engine(cm_limit)
full=((),(),(0,2,1,1,0,2,2))
ck("bound failure is fully atomic",full in el.explore(el.start[0]) and el.step(full,20,()) is None)
bad=cm.copy();bad[8]=c_rules+[template(40,[],[],[eff(3,1,one_m),eff(4,0,one_m),eff(6,0,cost)])]
eb=Engine(bad)
for i,s in enumerate(eb.start):
    total=s[2][0]
    fault=[[],[cmp(1,num(credit,terms=[[1,1],[2,1],[5,1],[6,1]]),num(credit,total))]]
    ck(f"mutant has a one-step conservation counterexample, initial {i+1}",ids(eb.explore(s,fault))==[40] and e.explore(e.start[i],fault) is None)
wrong=cm.copy();wrong[8]=[template(50,[],[],[eff(3,0,one)])]
ck("incompatible units rejected",failed(lambda:Engine(wrong),"counter effect"))

def bounded(e,q,target,limits,forbid=()):
    used=[0,0,0,0]; cases=[]
    def spend(i,n=1):
        if used[i]+n>limits[i]:return False
        used[i]+=n;return True
    def done(stop):
        all_covered=len(cases)==len(e.start)
        values={c[1] for c in cases}
        if (q==0 and 0 in values) or (q==1 and all_covered and values=={0}): out=0
        elif (q==1 and 1 in values) or (q==0 and all_covered and values=={1}): out=1
        else: out=2
        return [out,int(all_covered),stop,cases]
    def match(s):
        for b in e.domain_bindings(target[0]):
            if not spend(2):return 4,None
            if e.guards(s,target[1],b):return 0,list(b)
        return 0,None
    for start in e.start:
        if not spend(0):return done(2)
        if not spend(1):return done(3)
        seen={start}; queue=deque()
        stop,b=match(start)
        if stop:return done(stop)
        proof=[[],b] if b is not None else None
        if proof is None:queue.append((start,[]))
        while queue and proof is None:
            s,path=queue.popleft()
            for r,(bs,_,_) in sorted(e.rules.items()):
                for b in e.domain_bindings(bs):
                    if not spend(2):return done(4)
                    nxt=e.step(s,r,b,forbid)
                    if not nxt or nxt[0] in seen:continue
                    if not spend(1):return done(3)
                    end,delta=nxt
                    seen.add(end); history=path+[[r,list(b),delta]]
                    stop,target_binding=match(end)
                    if stop:return done(stop)
                    if target_binding is not None:
                        proof=[history,target_binding];break
                    queue.append((end,history))
                if proof is not None:break
        case=[start,0,proof] if proof is not None else [start,1,sorted(seen)]
        if not spend(3,len(cbor(case))):return done(5)
        cases.append(case)
        if len(cases)==len(e.start):return done(0)
        if case[1]==q:return done(1)
    raise AssertionError("empty initial set")

always_fails=Engine(skel([1],sorts=[[1,[1]]],initial=[([],[])]))
never=[[1],[[9,V(0),C(1)]]]
ck("budget exact closure for one target binding",bounded(always_fails,0,never,[1,1,1,100])[:3]==[1,1,0])
wide_fail=Engine(skel([1,2],sorts=[[1,[1,2]]],initial=[([],[])]))
two=[9,V(0),C(2)]
ck("budget applies to target bindings",bounded(wide_fail,0,[[1],[[9,V(0),C(1)],two]],[1,1,1,100])[:3]==[2,0,4])
sm=skel([1],counter=[[1,1,"count",1,0]],
        initial=[([],[0]),([],[1])])
mix=Engine(sm)
t=[[],[cmp(0,num("count",terms=[[1,1]]),num("count",1))]]
ck("state-level binding is distinct from initial ANY/EACH",bounded(mix,0,t,[2,2,2,128])[:3]==[0,1,0] and bounded(mix,1,t,[2,2,2,128])[:3]==[1,0,1])
ck("unexamined initials produce partial certificate",bounded(mix,0,t,[1,2,2,128])[:3]==[2,0,2])
ck("case-byte limit preserves sound verdicts",bounded(mix,1,t,[2,2,2,1])[:3]==[2,0,5])

# Bind the documented machine vector to the actual zero-step reference proof.
mini=skel([1],counter=[[1,1,"count",2,0]],initial=[([],[0])])
em=Engine(mini)
target=[[],[cmp(0,num("count",terms=[[1,1]]),num("count"))]]
model_bytes=wire(0,mini); md=sha256(model_bytes).digest()
query=[md,0,target,[],[1,1,4,128]]
query_bytes=wire(1,query);qd=sha256(query_bytes).digest()
out=em.explore(em.start[0],target)
ck("document vector is replayable zero step",out==(em.start[0],[],[]))
result=[md,qd]+bounded(em,0,target,[1,1,4,128])
ck("wire result matches declared proof and complete coverage",result[2:]==[0,1,0,[[out[0],0,[out[1],out[2]]]]])
result_bytes=wire(2,result)
ck("version binds wire digests",md!=sha256(cbor(["Molish",0,2,0,mini])).digest())
print(json.dumps({"passed":len(tested),"checks":tested,"wire":{"model":model_bytes.hex(),"query":query_bytes.hex(),"result":result_bytes.hex()}},ensure_ascii=False))
