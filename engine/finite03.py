from collections import deque
from itertools import product

def head(kind,n):
    assert 0 <= n < 2**32
    if n < 24: return bytes([(kind<<5)+n])
    for tag,size in ((24,1),(25,2),(26,4)):
        if n < 1 << (size*8): return bytes([(kind<<5)+tag])+n.to_bytes(size,"big")
def cbor(x):
    if type(x) is int:return head(0,x)
    if isinstance(x,bytes):return head(2,len(x))+x
    if isinstance(x,str):return head(3,len(x.encode()))+x.encode()
    if isinstance(x,(tuple,list)):return head(4,len(x))+b"".join(map(cbor,x))
    raise TypeError(x)
def wire(kind,x):return cbor(["Molish",0,3,kind,x])
def const(i):return [0,i]
def var(i):return [1,i]
V=var
C=const
def has(r,*t):return [2,r,list(t)]
def adds(r,*t):return [1,r,list(t)]
def drops(r,*t):return [2,r,list(t)]
def free(r,k,*t):return [8,r,k,list(t)]
def num(unit,c=0,terms=()):return [unit,c,list(terms)]
def cmp(op,a,b):return [7,op,a,b]
def eff(counter,direction,linear):return [3,counter,direction,linear]
def template(rid,binders,conditions,effects):
    return [1,rid,binders,sorted(conditions),sorted(effects),[]]
def skel(entities,sorts=(),relations=(),counter=(),tracks=(),ranges=(),static=(),initial=(),templates=()):
    core=[[[i,3,str(i)] for i in sorted(entities)],[],[],
          [[1,0,"symbolic-fixture","",[]]] if templates else [],
          [[1,[],[],[],[1],[]]] if templates else [],0,[],[0]]
    return [core,list(sorts),list(relations),list(counter),list(tracks),list(ranges),sorted(static),
            [1,[[[],sorted(facts),counts] for facts,counts in initial]],list(templates)]
def make_state(x):return (tuple(x[0]),tuple((r,tuple(args)) for r,args in x[1]),tuple(x[2]))

class Engine:
    def __init__(self,m):
        self.m=m
        entities, domain_records, slot_records, evidence, module_records, _, _, space = m[0]
        self.entities = {entity_id: kind for entity_id, kind, _ in entities}
        domains = {domain_id: (kind, set(codes)) for domain_id, kind, codes in domain_records}
        domains[0] = (0, {0, 1})
        slot_records = {record[0]: record for record in slot_records}
        self.slots = {slot: (domains[domain][1], mode) for slot, _, _, domain, mode in slot_records.values()}
        self.slot_id = {slot_id: index for index, slot_id in enumerate(self.slots)}
        self.parents, self.move_edges = {}, {}
        if space[0] == 1:
            self.parents = dict(space[1])
            self.move_edges = {(source, target): conditions for source, target, conditions in space[2]}
            if len(self.parents) != len(space[1]) or len(self.move_edges) != len(space[2]):
                raise ValueError("duplicate space record")
            for entity, slot in self.parents.items():
                _, owner, _, domain, _ = slot_records[slot]
                kind, values = domains[domain]
                if owner != entity or entity not in self.entities or kind != 1 or any(
                    self.entities.get(value) != 1 for value in values
                ):
                    raise ValueError("parent type")
            for source, target in self.move_edges:
                if source == target or self.entities.get(source) != 1 or self.entities.get(target) != 1:
                    raise ValueError("edge type")
            for conditions in self.move_edges.values():
                self.check_core_guards(conditions)
            remaining = {entity for entity in self.parents if self.entities[entity] == 1}
            while remaining:
                roots = {entity for entity in remaining if self.slots[self.parents[entity]][0].isdisjoint(remaining)}
                if not roots:
                    raise ValueError("possible containment cycle")
                remaining.difference_update(roots)
        elif space != [0]:
            raise ValueError("space")
        self.sort={i:set(z) for i,z in m[1]}
        self.rels={r:(tys,mode,keys) for r,tys,mode,keys in m[2]}
        self.count={i:(unit,mx,mode) for i,_,unit,mx,mode in m[3]}
        self.counter_id={i:n for n,i in enumerate(self.count)}
        self.track=dict(m[4])
        self.site_to_track={v:k for k,values in self.track.items() for v in values}
        self.ranges={r:(k,a,b) for r,k,a,b in m[5]}
        self.static=set((r,tuple(ts)) for r,ts in m[6])
        initial = m[7]
        if initial[0] != 1:
            raise ValueError("unsupported initial-state encoding")
        self.start = [make_state(state) for state in initial[1]]
        modules = {module[0]: module for module in module_records}
        if len(modules) != len(module_records):
            raise ValueError("duplicate module")
        self.evidence = {record[0]: record for record in evidence}
        self.rule_evidence = {}
        self.rules = {}
        for _, _, _, module_when, _, _ in module_records:
            self.check_core_guards(module_when)
        for record in evidence:
            self.check_core_guards(record[4])
            if any(op != 0 or self.slots[slot][1] != 1 for op, slot, _ in record[4]):
                raise ValueError("evidence scope")
        for module_id, rule_id, binders, guards, effects, direct_evidence in m[8]:
            if module_id not in modules:
                raise ValueError("unknown module")
            _, _, _, module_when, inherited_evidence, _ = modules[module_id]
            self.add_rule(rule_id, binders, module_when + guards, effects, inherited_evidence + direct_evidence)
        for _, _, _, module_when, inherited_evidence, fixed_rules in modules.values():
            for rule_id, guards, writes, direct_evidence in fixed_rules:
                self.check_core_guards(guards)
                effects = [[0, slot_id, value] for slot_id, value in writes]
                self.add_rule(rule_id, [], module_when + guards, effects, inherited_evidence + direct_evidence)
        if any(a>=b or a<0 or b>len(self.track[k]) for k,a,b in self.ranges.values()):raise ValueError("range")
        for _,g,es in self.rules.values():
            for op,r,*a in es:
                if op==3 and (self.count[r][2]!=0 or not self.unit(a[1],self.count[r][0])):raise ValueError("counter effect")
        if not self.start or not all(self.valid(st) for st in self.start):
            raise ValueError("initial")

    def check_core_guards(self, conditions):
        for op, first, second in conditions:
            if op == 0 and first in self.slots and second in self.slots[first][0]:
                continue
            if op == 1 and first in self.entities and self.entities.get(second) == 1:
                continue
            raise ValueError("invalid core guard")

    def add_rule(self, rule_id, binders, guards, effects, evidence):
        if rule_id in self.rules:
            raise ValueError("duplicate rule")
        if any(condition[0] not in range(10) for condition in guards):
            raise ValueError("unsupported rule guard")
        if any(effect[0] not in range(4) for effect in effects):
            raise ValueError("unsupported rule effect")
        if not evidence or any(evidence_id not in self.evidence for evidence_id in evidence):
            raise ValueError("rule evidence")
        self.rule_evidence[rule_id] = sorted(set(evidence))
        self.rules[rule_id] = [binders, guards, effects]

    def applicable_evidence(self, state, rule_id):
        return [
            self.evidence[evidence_id] for evidence_id in self.rule_evidence[rule_id]
            if self.guards(state, self.evidence[evidence_id][4], ())
        ]

    def containers(self, state, entity):
        seen = {entity}
        while entity in self.parents:
            entity = state[0][self.slot_id[self.parents[entity]]]
            if entity in seen:
                raise ValueError("cyclic containment")
            seen.add(entity)
            yield entity
    def unit(self,x,u):
        return x[0]==u and all(self.count[c][0]==u for c,_ in x[2])
    def args(self,ts,b):
        return tuple(b[v] if op==1 else v for op,v in ts)
    def expr(self,x,s):
        return x[1]+sum(s[2][self.counter_id[c]]*k for c,k in x[2])
    def typed(self,r,ts):
        types=self.rels[r][0]
        return len(types)==len(ts) and all(t in self.sort[s] for s,t in zip(types,ts))
    def facts(self,s,r):
        return self.static if self.rels[r][1]==0 else set(s[1])
    def guards(self,s,g,b):
        for op,*a in g:
            if op == 0:
                slot, value = a
                if s[0][self.slot_id[slot]] != value:
                    return False
            elif op == 1:
                entity, compartment = a
                if compartment not in self.containers(s, entity):
                    return False
            elif op in (2,3):
                rel,ts=a;t=self.args(ts,b)
                if not self.typed(rel,t) or (((rel,t) in self.facts(s,rel))!=(op==2)):return False
            elif op==4:
                track,prev,nxt=self.args(a,b)
                if track not in self.track or not any(x==prev and y==nxt for x,y in zip(self.track[track],self.track[track][1:])):return False
            elif op in (5,6):
                r,loc=self.args(a,b)
                if r not in self.ranges:return False
                track,i,j=self.ranges[r]
                if op==5 and loc not in self.track[track][i:j] or op==6 and loc!=track:return False
            elif op==7:
                c,x,y=a
                if not self.unit(x,y[0]) or not self.unit(y,x[0]): raise ValueError("comparison units")
                l,r=self.expr(x,s),self.expr(y,s)
                if not (l==r,l!=r,l<r,l<=r,l>r,l>=r)[c]:return False
            elif op==8:
                r,i,ts=a
                pos=self.rels[r][2][i]
                t=self.args(ts,b)
                if len(t)!=len(pos) or any(x not in self.sort[self.rels[r][0][j]] for x,j in zip(t,pos)):return False
                if any(r==rr and tuple(x[j] for j in pos)==t for rr,x in self.facts(s,r)):return False
            elif op==9:
                x,y=self.args(a,b)
                if x==y:return False
            else:raise ValueError("operation")
        return True
    def domain_bindings(self,sorts):return product(*(sorted(self.sort[t]) for t in sorts))
    def valid(self,s):
        if len(s[0]) != len(self.slots) or any(
            value not in slot[0] for value, slot in zip(s[0], self.slots.values())
        ):
            return False
        try:
            for entity in self.parents:
                if any(self.entities.get(parent) != 1 for parent in self.containers(s, entity)):
                    return False
        except ValueError:
            return False
        if s[1] != tuple(sorted(set(s[1]))) or any(
            rel not in self.rels or self.rels[rel][1] != 1 for rel, _ in s[1]
        ):
            return False
        if len(s[2])!=len(self.count) or any(not 0<=x<=v[1] for v,x in zip(self.count.values(),s[2])):return False
        for r,(args,mode,keys) in self.rels.items():
            relevant=[x for rr,x in self.facts(s,r) if rr==r]
            if any(not self.typed(r,x) for x in relevant):return False
            for k in keys:
                if len(set(tuple(x[i] for i in k) for x in relevant))!=len(relevant):return False
        return True
    def step(self,s,rid,b,forbid=()):
        sorts,g,es=self.rules[rid]
        if len(sorts)!=len(b) or any(x not in self.sort[t] for x,t in zip(b,sorts)):return
        if [0,rid] in forbid or [3,rid,list(b)] in forbid or not self.guards(s,g,b):return
        before=set(s[1]);add=set();remove=set();counts=list(s[2]);updated=set()
        slot_updates = {}
        for op,r,*a in es:
            if op == 0:
                value = a[0]
                domain, mode = self.slots[r]
                if mode != 0 or value not in domain or slot_updates.setdefault(r, value) != value:
                    return
            elif op in (1,2):
                t=self.args(a[0],b)
                if self.rels[r][1]!=1 or not self.typed(r,t):return
                (add if op==1 else remove).add((r,t))
            elif op==3:
                if r in updated:return
                updated.add(r)
                counts[self.counter_id[r]]+=self.expr(a[1],s)*(1 if a[0]==0 else -1)
            else:raise ValueError("test operation")
        if add & remove:return
        facts=(before-remove)|add
        slots = list(s[0])
        for slot, value in slot_updates.items():
            slots[self.slot_id[slot]] = value
        ns=(tuple(slots),tuple(sorted(facts)),tuple(counts))
        if not self.valid(ns):return
        for slot in self.parents.values():
            index = self.slot_id[slot]
            source, target = s[0][index], ns[0][index]
            if source != target:
                move_guard = self.move_edges.get((source, target))
                if move_guard is None or not self.guards(s, move_guard, ()):
                    return
        for op, *args in forbid:
            if op == 1:
                slot, value = args
                index = self.slot_id[slot]
                if s[0][index] != value and ns[0][index] == value:
                    return
            elif op == 2:
                entity, compartment = args
                if compartment not in self.containers(s, entity) and compartment in self.containers(ns, entity):
                    return
            elif op not in (0, 3):
                raise ValueError("unsupported intervention")
        delta=[[1,r,list(t)] for r,t in facts-before]+[[2,r,list(t)] for r,t in before-facts]
        delta += [[3,r,counts[i]] for r,i in self.counter_id.items() if s[2][i]!=counts[i]]
        delta += [[0, slot, value] for slot, value in slot_updates.items() if value != s[0][self.slot_id[slot]]]
        return ns,sorted(delta)
    def edges(self,s,forbid=()):
        for r,(bs,_,_) in sorted(self.rules.items()):
            for b in self.domain_bindings(bs):
                step=self.step(s,r,b,forbid)
                if step:yield step[0],[r,list(b),step[1]]
    def trace(self,initial,events,forbid=()):
        s=initial
        for r,b,delta in events:
            n=self.step(s,r,b,forbid)
            if not n or n[1]!=delta:return
            s=n[0]
        return s
    def explore(self,start,target=None,forbid=()):
        seen={start}
        queue=deque([(start,[])])
        while queue:
            s,path=queue.popleft()
            if target is not None:
                binders,guards=target
                for b in self.domain_bindings(binders):
                    if self.guards(s,guards,b):return s,path,list(b)
            for end,ev in self.edges(s,forbid):
                if end not in seen:
                    seen.add(end);queue.append((end,path+[ev]))
        return seen if target is None else None
