from copy import deepcopy
from pathlib import Path
import json

from finite03 import C, Engine, adds, cbor, cmp, drops, has, num, skel, template
from molish04 import (
    assemble, claim_ids, detail, dg, eligibility, locked, make_query, make_result,
    model04, pack, parse, project, snapshot, submit, verify_query, verify_view,
)

checked=[]
def ck(name,ok):
    assert ok,name
    checked.append(name)
def reject(fn,expected):
    try:fn()
    except ValueError as e:return str(e)==expected
    return False

unit="gate"
zero=num(unit)
one=num(unit,1)
gate=num(unit,terms=[[1,1]])
move=template(20,[],[has(1,C(1),C(10)),cmp(5,gate,one)],
    [adds(1,C(1),C(11)),drops(1,C(1),C(10))])
fine_move=template(20,[],[has(1,C(1),C(10)),has(2,C(1)),cmp(5,gate,one)],
    [adds(1,C(1),C(11)),drops(1,C(1),C(10))])
contact=template(10,[],[has(1,C(1),C(10))],[adds(2,C(1))])
def core(fine=False):
    rs=[[1,[1,2],1,[[0]]]]+([[2,[1],1,[]]] if fine else [])
    x=skel([1,2,10,11,12,13],sorts=[[1,[1]],[2,[10,11]]],relations=rs,
           counter=[[1,1,unit,2,1],[2,2,unit,2,1]],
           initial=[([[1,[1,10]]],[1,0]),([[1,[1,10]]],[1,1])],
           templates=[contact,fine_move] if fine else [move])
    for e in x[0][0]:
        if e[0] in (10,11):e[1]=1
    x[0][2]=[[1,1,"context",0,1]]
    x[0][3]+=[[2,2,"example paper","A only",[[0,1,0]]],[3,1,"example data","B only",[[0,1,1]]]]
    x[7][1][0][0]=[0];x[7][1][1][0]=[1]
    return x
src=[[1,0,"publisher","note","1","table A",[0]],[2,1,"archive","data","1","entry A",[1,dg(b"fixture data")]],
     [3,2,"model","proposal","1","run",[0]]]
cl=[[1,1,2,[1,20],0],[2,2,2,[1,20],1],[3,3,3,[0,1],2]]
childlock,child=locked("site",2,[[1,0,[3]]])
rootlock,root=locked("complex",3,[[1,0,[3]],[2,2,[unit,1]]],[[5,childlock]])
catalog={rootlock[3]:root,childlock[3]:child}
roots=[[1,rootlock,[[1,1],[2,1]]],[2,rootlock,[[1,2],[2,2]]]]
sel=[[1,[5],12,[[1,12]]]]
basecore=core()
finecore=core(True)
coarse=model04(basecore,roots,sources=src,claims=cl)
detailed=model04(basecore,roots,sel,src,cl)
fmodel=model04(finecore,roots,sel,src,cl)
a,active,_=assemble(coarse,{rootlock[3]:root})
ck("independent root instances share one lock",active[1,()][0]==1 and active[2,()][0]==2 and roots[0][1]==roots[1][1] and roots[0][2][-1]!=roots[1][2][-1])
ck("only selected definitions are needed",len(active)==2)
ck("undeclared fine detail is a diagnostic",reject(lambda:detail(active,1,[5]),"DETAIL_NOT_SELECTED"))
active2=assemble(detailed,catalog)[1]
ck("selected fine part binds a stable entity",detail(active2,1,[5])==12)
ck("semantic selection changes outer digest",dg(coarse)!=dg(detailed) and parse(coarse,0)[0]==parse(detailed,0)[0])
ck("selected child is required",reject(lambda:assemble(detailed,{rootlock[3]:root}),"MISSING_DEFINITION"))
ck("definition content hash mismatch",reject(lambda:assemble(detailed,{rootlock[3]:root,childlock[3]:child+b"\x00"}),"DEFINITION_DIGEST"))
badroot=[row[:] for row in roots]
badroot[0]=[1,[*rootlock[:2],"2",rootlock[3]],roots[0][2]]
ck("version metadata mismatch",reject(lambda:assemble(model04(basecore,badroot),catalog),"DEFINITION_IDENTITY"))
ck("bad port role",reject(lambda:assemble(model04(basecore,roots,[[1,[5],12,[[1,10]]]]),catalog),"PORT_TYPE"))
ck("parts cannot reuse root entity ID",reject(lambda:assemble(model04(basecore,roots,[[1,[5],2,[[1,2]]]]),catalog),"DUPLICATE_INSTANCE"))
ck("missing expansion parent rejected",reject(lambda:assemble(model04(basecore,roots,[[1,[5,6],12,[[1,12]]]]),catalog),"PARENT_NOT_SELECTED"))
alt,altbytes=locked("complex",3,[[1,0,[3]],[2,2,[unit,1]]],[])
ck("conflicting lock for same publisher identity",reject(lambda:assemble(model04(basecore,[roots[0],[2,alt,roots[1][2]]]),{**catalog,alt[3]:altbytes}),"LOCK_CONFLICT"))

ce=Engine(basecore);fe=Engine(finecore)
target=[[],[has(1,C(1),C(11))]]
q=make_query(coarse,target)
fq=make_query(fmodel,target)
cwin=ce.explore(ce.start[0],target); fwin=fe.explore(fe.start[0],target)
ck("coarse executes independently of absent detail",len(cwin[1])==1 and len(fwin[1])==2)
ck("conflicting claims preserved within context A",claim_ids(coarse,ce.start[0])==[1,2])
ck("claims filtered in context B",claim_ids(coarse,ce.start[1])==[3])
ck("locked source bytes verified and changed bytes rejected",assemble(coarse,catalog,{2:b"fixture data"})[2][2]==1 and reject(lambda:assemble(coarse,catalog,{2:b"altered"}),"SOURCE_DIGEST"))
ck("typed invalid claim target rejected",reject(lambda:assemble(model04(basecore,roots,sources=src,claims=[[1,1,2,[2,1,[1,12]],0]]),catalog),"CLAIM_TARGET"))
ck("AI proposal binds new validated candidate",submit(coarse,pack(7,[dg(coarse),3,detailed]),catalog)==dg(detailed))
ck("stale proposal base rejected",reject(lambda:submit(detailed,pack(7,[dg(coarse),3,detailed]),catalog),"BASE_BINDING"))
ck("AI proposal source must be AI",reject(lambda:submit(coarse,pack(7,[dg(coarse),1,detailed]),catalog),"AI_ORIGIN"))
ck("inner and outer digests both checked",reject(lambda:verify_query(coarse,pack(1,[dg(coarse),parse(fq,1)[1]])),"QUERY_BINDING"))
ck("expansion invalidates outer query binding",reject(lambda:verify_query(detailed,q),"QUERY_BINDING"))

fr=make_result(fmodel,fq,fe.start[0],fwin[1])
cr=make_result(coarse,q,ce.start[0],cwin[1])
fid=dg(cbor(fe.start[0])); cid=dg(cbor(ce.start[0]))
fb=[dg(fmodel),dg(fq),dg(fr),fid]; cb=[dg(coarse),dg(q)]
mp=[[[1,1]],[[1,1],[2,2]],[[[1,[1,10]],[1,[1,10]]],[[1,[1,11]],[1,[1,11]]]]]
events=[[10,[],[0]],[20,[],[1,20,[]]]]
goodproj=pack(6,[fb,cb,mp,events])
ck("fine contact hidden, coarse move replayed",project(fmodel,fq,fr,coarse,q,goodproj)[:2]==(cwin[0],cwin[1]))
ck("hide observable location change rejected",reject(lambda:project(fmodel,fq,fr,coarse,q,pack(6,[fb,cb,mp,[[10,[],[0]],[20,[],[0]]]])),"HIDDEN_CHANGE"))
ck("missing event mapping rejected",reject(lambda:project(fmodel,fq,fr,coarse,q,pack(6,[fb,cb,mp,events[:1]])),"UNMAPPED_EVENT"))
ck("incomplete state mapping rejected",reject(lambda:project(fmodel,fq,fr,coarse,q,pack(6,[fb,cb,[mp[0],[],mp[2]],events])),"INCOMPLETE_MAP"))
ck("reference to undefined projected fact rejected",reject(lambda:project(fmodel,fq,fr,coarse,q,pack(6,[fb,cb,[mp[0],mp[1],[[[3,[1,10]],[1,[1,10]]]]],events])),"MAP_FACT_TYPE"))
cqblock=make_query(coarse,target,[[0,20]])
ck("coarse intervention still applies on projection",reject(lambda:project(fmodel,fq,fr,coarse,cqblock,pack(6,[fb,[dg(coarse),dg(cqblock)],mp,events])),"COARSE_STEP"))
cqold=make_query(coarse,[[],[has(1,C(1),C(10))]])
ck("coarse target is separately checked",reject(lambda:project(fmodel,fq,fr,coarse,cqold,pack(6,[fb,[dg(coarse),dg(cqold)],mp,events])),"COARSE_GOAL"))
badcore=deepcopy(basecore)
badcore[8][0][3]=sorted([has(1,C(1),C(10)),cmp(0,gate,zero)])
badcoarse=model04(badcore,roots,sources=src,claims=cl)
bq=make_query(badcoarse,target)
ck("mapping cannot bypass coarse model guard",reject(lambda:project(fmodel,fq,fr,badcoarse,bq,pack(6,[fb,[dg(badcoarse),dg(bq)],mp,events])),"COARSE_STEP"))
ck("wrong projection binding rejected",reject(lambda:project(fmodel,fq,fr,coarse,q,pack(6,[fb,[dg(detailed),dg(q)],mp,events])),"PROJECTION_BINDING"))

view=pack(4,[dg(coarse),dg(q),dg(cr),cid,[],[0]])
assets=[[1,1,dg(b"asset"),"asset:example"]]
styled=pack(4,[dg(coarse),dg(q),dg(cr),cid,assets,[1,[[0,0],[1,400]]]])
ck("optional geometry and visual time leave logical replay identical",dg(view)!=dg(styled) and verify_view(coarse,q,cr,view)==verify_view(coarse,q,cr,styled))
badview=pack(4,[dg(coarse),dg(q),dg(cr),cid,assets,[1,[[0,200],[1,100]]]])
ck("invalid visual schedule rejected",reject(lambda:verify_view(coarse,q,cr,badview),"SCHEDULE"))
ck("orphan visual asset rejected",reject(lambda:verify_view(coarse,q,cr,pack(4,[dg(coarse),dg(q),dg(cr),cid,[[1,99,dg(b"asset"),"asset:example"]],[0]])),"VIEW_ASSET"))
ck("replay rejects old digest paired with new model",reject(lambda:verify_view(detailed,q,cr,view),"VIEW_BINDING"))
each_raw=parse(parse(q,1)[1],1,3)
each_raw[1]=1
eq=pack(1,[dg(coarse),pack(1,each_raw,3)])
pr=make_result(coarse,eq,ce.start[0],cwin[1],aggregate=2)
pres=pack(4,[dg(coarse),dg(eq),dg(pr),cid,[],[0]])
ck("verified case from overall UNKNOWN can play",verify_view(coarse,eq,pr,pres)[1]==2)
badtrace=deepcopy(cwin[1]);badtrace[0][2]=[]
forged=make_result(coarse,q,ce.start[0],badtrace)
badtraceview=pack(4,[dg(coarse),dg(q),dg(forged),cid,[],[0]])
ck("forged exact trace rejected",reject(lambda:verify_view(coarse,q,forged,badtraceview),"TRACE"))
shot0=parse(snapshot(coarse,q,cr,cid,0),5);shot1=parse(snapshot(coarse,q,cr,cid,1),5)
ck("KG snapshot preserves scope and different state facts",shot0[:4]==shot1[:4] and shot0[6]==[[0],[[1,[1,10]]],[1,0]] and shot1[6]==[[0],[[1,[1,11]]],[1,0]] and shot1[7]==[1,2])
ck("invalid snapshot step rejected",reject(lambda:snapshot(coarse,q,cr,cid,2),"STEP"))

species=[[1,1,10,"entity_count",[1,1,1]]]
def req(law,guard=0,amount=None):
    things=deepcopy(species)
    if amount is not None:things[0][4]=amount
    return pack(8,[dg(coarse),0,"s",things,[[20,[],[[1,0,1]],law,guard]]])
check=parse(eligibility(coarse,req([0])),9)
ck("qualitative model lacks declared physical law",check[2:]==[0,[0]])
law=[1,"entity_count","s",dg(b"toy-law")]
ck("adapter reports readiness for mapping only",parse(eligibility(coarse,req(law)),9)[2:]==[1,[]])
ck("missing initial quantities identified",parse(eligibility(coarse,req(law,amount=[0])),9)[2:]==[0,[1]])
ck("unit mismatch and unsupported guard diagnosed",parse(eligibility(coarse,req([1,"entity_count","ms",law[3]],1)),9)[2:]==[0,[2,3]])
ck("noncanonical amount rejected",reject(lambda:eligibility(coarse,req(law,amount=[1,2,2])),"AMOUNT"))

mini_core=skel([1],counter=[[1,1,"count",2,0]],initial=[([],[0])])
ref,defn=locked("minimal",3,[[1,0,[3]]])
minimal=model04(mini_core,[[1,ref,[[1,1]]]])
mquery=make_query(minimal,[[],[cmp(0,num("count",terms=[[1,1]]),num("count"))]])
ck("published vectors decode and assemble",assemble(minimal,{ref[3]:defn})[1][1,()][0]==1 and verify_query(minimal,mquery)[0]==dg(parse(minimal,0)[0]))
ck("trailing bytes rejected",reject(lambda:parse(minimal+b"\x00",0),"ENVELOPE"))
ck("wrong 0.4 frame version rejected",reject(lambda:parse(pack(0,parse(minimal,0),3),0),"ENVELOPE"))
ck("nonminimal integer rejected",reject(lambda:parse(minimal[:8]+b"\x18"+minimal[8:],0),"NON_CANONICAL"))

text = Path(__file__).with_name("Molish-0.4-spec.md").read_text()
vectors="\n".join(f"{n} ({len(b)} bytes) {b.hex()}\nSHA-256 {dg(b).hex()}" for n,b in
                  [("definition",defn),("model",minimal),("query",mquery)])
assert vectors in text
published_traces = text.split("### 同一轨迹的粗细层对照", 1)[1].split("## 附录", 1)[0]
for trace in (fwin[1], cwin[1], events):
    assert json.dumps(trace, separators=(",", ":")) in published_traces
print(json.dumps({"passed":len(checked),"checks":checked,"vectorLengths":[len(defn),len(minimal),len(mquery)]},ensure_ascii=False))
