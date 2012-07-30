from pylab import *
from collections import Counter,defaultdict
import glob,re,heapq,os,cPickle
import ngraphs as ng

class Edge:
    def __init__(self,**kw):
        self.__dict__.update(kw)
    def __str__(self):
        return self.__repr__()
    def __repr__(self):
        return "<%d:%d [%s] %.2f %d:%d>"%(self.start,self.stop,self.cls,self.cost,self.seg[0],self.seg[1])

class Lattice:
    def __init__(self,**kw):
        self.maxws = 20.0
        self.maxcost = 20.0
        self.mismatch = 30.0
        self.accept = None
        self.__dict__.update(kw)
    def addEdge(self,start=None,stop=None,cost=None,cls=None,seg=(0,0)):
        self.states.add(start)
        self.states.add(stop)
        self.edges[start].append(Edge(start=start,stop=stop,cost=cost,cls=cls,seg=seg))
    def readLattice(self,fname):
        self.states = set()
        self.edges = defaultdict(list)
        with open(fname) as stream:
            for line in stream.readlines():
                f = line.split()
                if f[0]=="segment":
                    first,last = [int(x) for x in f[2].split(":")]
                    # we put the actual OCR segment numbers at 10x the state;
                    # that gives us intermediate states to insert spaces and extra
                    # characters
                    st_start = 2*first
                    st_extra = 2*last+1
                    st_next = 2*last+2
                    ws,nows = [float(x) for x in f[4:6]]
                    ws = minimum(ws,self.maxws)
                    nows = minimum(nows,self.maxws)
                    if self.edges[st_extra]==[]:
                        # skip or replace
                        self.addEdge(start=st_start,stop=st_extra,cost=self.mismatch,cls="")
                        self.addEdge(start=st_start,stop=st_extra,cost=self.mismatch,cls="~")
                        # insert space / no space
                        self.addEdge(start=st_extra,stop=st_next,cost=ws,cls=" ")
                        self.addEdge(start=st_extra,stop=st_next,cost=nows,cls="")
                        # insert arbitrary (this implies "no space")
                        self.addEdge(start=st_extra,stop=st_next,cost=self.mismatch,cls="~")
                elif f[0]=="chr":
                    cost = minimum(float(f[3])+nows,self.maxcost)
                    self.addEdge(start=st_start,stop=st_extra,cost=cost+nows,cls=f[4],seg=(first,last))
        return self
    def isAccept(self,i):
        if self.accept is None:
            self.accept = [self.lastState()]
        return i in self.accept
    def latticeGraph(self):
        import pydot
        graph = pydot.Dot("lattice",graph_type="digraph",rankdir="LR")
        for s in sorted(list(self.states)):
            graph.add_node(pydot.Node(str(s)))
        for s in sorted(list(self.states)):
            for edge in self.edges[s]:
                cls = edge.cls
                if cls in ["'",'"']: cls = "<QUOTE>"
                elif cls=="": cls = "<EPS>"
                elif cls==" ": cls = "<SPC>"
                graph.add_edge(pydot.Edge(src=str(edge.start),dst=str(edge.stop),label='"%s/%s"'%(cls,edge.cost)))
        return graph
    def showLattice(self):
        graph = self.latticeGraph()
        with open("temp.png","w") as stream: 
            stream.write(graph.create_png())
        os.system("eog temp.png&")
    def startState(self):
        return min(self.states)
    def lastState(self):
        return max(self.states)
    def classes(self):
        edges = reduce(lambda x,y:x+y,[[e for e in l] for k,l in self.edges.items()])
        classes = set([e.cls for e in edges])
        return sorted(list(classes))

