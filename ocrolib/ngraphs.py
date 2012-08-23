# TODO:
# - handle UTF-8 inputs correctly

from pylab import *
from collections import Counter,defaultdict
import glob,re,heapq,os,cPickle
import codecs

def method(cls):
    """Adds the function as a method to the given class."""
    import new
    def _wrap(f):
        cls.__dict__[f.func_name] = new.instancemethod(f,None,cls)
        return None
    return _wrap

replacements = [
    (r'[\0-\x1f]',''), # get rid of weird control characters
    (r'\s+',' '),     # replace multiple spaces
    (r'[~]',""),      # replace rejects with nothing

    # single quotation marks
    (r"`","'"),       # grave accent
    (u"\u00b4","'"),  # acute accent
    (u"\u2018","'"),  # left single quotation mark
    (u"\u2019","'"),  # right single quotation mark
    (u"\u017f","s"),  # Fraktur "s" glyph
    (u"\u021a",","),  # single low quotation mark

    # double quotation marks
    (r'"',"''"),      # typewriter double quote
    (r'``',"''"),     # replace fancy double quotes
    (r"``","''"),     # grave accents used as quotes
    (r'"',"''"),      # replace fancy double quotes
    (u"\u201c","''"), # left double quotation mark
    (u"\u201d","''"), # right double quotation mark
    (u"\u201e",",,"), # lower double quotation mark
    (u"\u201f","''"), # reversed double quotation mark
    ]

replacements2 = replacements + [
    (r'[0-9]','9'), # don't try to model individual digit frequencies
    (r'[^-=A-Za-z0-9.,?:()"/\' ]','!'), # model other special characters just as '!'
    ]

def rsample(dist):
    v = add.accumulate(dist)
    assert abs(v[-1]-1)<1e-3
    val = rand()
    return searchsorted(v,val)

class NGraphs:
    """A class representing n-graph models, that is
    $P(c_i | c_{i-1} ... c_{i_n})$, where the $c_i$ are
    characters."""
    def __init__(self,N=4,replacements=replacements):
        self.N = N
        self.replacements = replacements
    def lineproc(self,s):
        """Preprocessing for the line (and also lattice output strings).
        This is used to normalize quotes, remove illegal characters,
        and collapse some character classes (e.g., digits) into a single
        representative."""
        for regex,subst in self.replacements:
            s = re.sub(regex,subst,s,flags=re.U)
        return s
    def computeNGraphs(self,fnames,n):
        """Given a set of text file names, compute a counter
        of n-graphs in those files, after performing the regular
        expression edits in `self.replacement`."""
        counter = Counter()
        lineskip = 0
        linelimit = 2000
        for fnum,fname in enumerate(fnames):
            print fnum,"of",len(fnames),":",fname
            if fname.startswith("lineskip="):
                lineskip = int(fname.split("=")[1])
                print "changing lineskip to",lineskip
                continue
            if fname.startswith("linelimit="):
                linelimit = int(fname.split("=")[1])
                print "changing linelimit to",linelimit
                continue
            with codecs.open(fname,"r","utf-8") as stream:
                for lineno,line in enumerate(stream.readlines()):
                    assert type(line)==unicode
                    if lineno<lineskip: continue
                    if lineno>=linelimit+lineskip: break
                    line = line[:-1]
                    if len(line)<3: continue
                    line = self.lineproc(line)
                    line = "_"*(n-1)+line+"_"*(n-1)
                    for i in range(len(line)-n):
                        sub = line[i:i+n]
                        counter[sub] += 1
        return counter
    def buildFromFiles(self,fnames,n):
        """Given a set of files, build the log posteriors."""
        print "reading",len(fnames),"files"
        counter = self.computeNGraphs(fnames,n)
        print "got",sum(counter.values()),"%d-graphs"%(n,)
        self.computePosteriors(counter)
        print "done building lposteriors"
    def computePosteriors(self,counter):
        """Given a `counter` of all n-graphs, compute
        (log) conditional probabilities."""
        self.N = len(counter.items()[0][0])
        ngrams = defaultdict(list)
        for k,v in counter.items():
            ngrams[k[:-1]].append((k,v))
        lposteriors = {}
        for prefix in ngrams.keys():
            ps = [(k[-1],v) for k,v in ngrams[prefix]] + [("~",1)]
            total = sum([v for k,v in ps])
            total = log(total)
            ps = {k : total-log(v) for k,v in ps}
            lposteriors[prefix] = ps
        self.lposteriors = lposteriors
    def sample(self,n=80,prefix=None):
        """Sample from the n-graph model.  This gives a fairly
        good impression of how well the n-graph model models
        text."""
        if prefix is None:
            prefix = "_"*self.N
        for i in range(n):
            lposteriors = self.lposteriors.get(prefix[-self.N+1:])
            if lposteriors is None:
                prefix += chr(ord("a")+int(rand()*26))
            else:
                items = [(k,p) for k,p in lposteriors.items() if k not in ["~","_"]]
                items += [(" ",10.0)]
                ks = [k for k,p in items]
                ps = array([p for k,p in items],'f')
                ps = exp(-ps)
                ps /= sum(ps)
                j = rsample(ps)
                prefix += ks[j]
        return prefix[self.N:]

