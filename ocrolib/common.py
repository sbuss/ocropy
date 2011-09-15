################################################################
### common functions for data structures, file name manipulation, etc.
################################################################

import os,os.path,re,numpy,unicodedata,sys,warnings,inspect,glob,traceback
import numpy
from numpy import *
from scipy.misc import imsave
from scipy.ndimage import interpolation,measurements,morphology

import utils
import docproc
import ligatures
import fstutils
import openfst
import segrec
import ocrofst
import ocrorast
import ocrolseg
import ocropreproc

import cPickle as pickle
pickle_mode = 2

from pycomp import PyComponent
from ocroio import renumber_labels
from ocroold import RegionExtractor,Grouper,StandardGrouper

################################################################
### Simple record object.
################################################################

class Record:
    def __init__(self,**kw):
        self.__dict__.update(kw)
    def like(self,obj):
        self.__dict__.update(obj.__dict__)
        return self

################################################################
### Histograms
################################################################

def chist(l):
    counts = {}
    for c in l:
        counts[c] = counts.get(c,0)+1
    hist = [(v,k) for k,v in counts.items()]
    return sorted(hist,reverse=1)

################################################################
### Environment functions
################################################################

def number_of_processors():
    try:
        return int(os.popen("cat /proc/cpuinfo  | grep 'processor.*:' | wc -l").read())
    except:
        return 1

################################################################
### exceptions
################################################################

class Unimplemented():
    def __init__(self,s):
        Exception.__init__(self,inspect.stack()[1][3])

class BadClassLabel(Exception):
    def __init__(self,s):
        Exception.__init__(self,s)

class RecognitionError(Exception):
    def __init__(self,explanation,**kw):
        self.context = kw
        s = [explanation]
        s += ["%s=%s"%(k,summary(kw[k])) for k in kw]
        message = " ".join(s)
        Exception.__init__(self,message)

def check_valid_class_label(s):
    if type(s)==unicode:
        if re.search(r'[\0-\x20]',s):
            raise BadClassLabel(s)
    elif type(s)==str:
        if re.search(r'[^\x21-\x7e]',s):
            raise BadClassLabel(s)
    else:
        raise BadClassLabel(s)

def summary(x):
    if type(x)==numpy.ndarray:
        return "<ndarray %s %s>"%(x.shape,x.dtype)
    if type(x)==str and len(x)>10:
        return '"%s..."'%x
    if type(x)==list and len(x)>10:
        return '%s...'%x
    return str(x)

################################################################
### file name manipulation
################################################################

def findfile(name):
    """Find some OCRopus-related resource by looking in a bunch off standard places.
    (FIXME: The implementation is pretty adhoc for now.
    This needs to be integrated better with setup.py and the build system.)"""
    local = "/usr/local/share/ocropus/"
    path = name
    if os.path.exists(path) and os.path.isfile(path): return path
    path = local+name
    if os.path.exists(path) and os.path.isfile(path): return path
    path = local+"/gui/"+name
    if os.path.exists(path) and os.path.isfile(path): return path
    path = local+"/models/"+name
    if os.path.exists(path) and os.path.isfile(path): return path
    path = local+"/words/"+name
    if os.path.exists(path) and os.path.isfile(path): return path
    _,tail = os.path.split(name)
    path = tail
    if os.path.exists(path) and os.path.isfile(path): return path
    path = local+tail
    if os.path.exists(path) and os.path.isfile(path): return path
    raise IOError("file '"+path+"' not found in . or /usr/local/share/ocropus/")

def finddir(name):
    """Find some OCRopus-related resource by looking in a bunch off standard places.
    (This needs to be integrated better with setup.py and the build system.)"""
    local = "/usr/local/share/ocropus/"
    path = name
    if os.path.exists(path) and os.path.isdir(path): return path
    path = local+name
    if os.path.exists(path) and os.path.isdir(path): return path
    _,tail = os.path.split(name)
    path = tail
    if os.path.exists(path) and os.path.isdir(path): return path
    path = local+tail
    if os.path.exists(path) and os.path.isdir(path): return path
    raise IOError("file '"+path+"' not found in . or /usr/local/share/ocropus/")

def allsplitext(path):
    """Split all the pathname extensions, so that "a/b.c.d" -> "a/b", ".c.d" """
    match = re.search(r'((.*/)*[^.]*)([^/]*)',path)
    if not match:
        return path,""
    else:
        return match.group(1),match.group(3)

def write_text(file,s):
    """Write the given string s to the output file."""
    with open(file,"w") as stream:
        if type(s)==unicode: s = s.encode("utf-8")
        stream.write(s)

def expand_args(args):
    if len(args)==1 and os.path.isdir(args[0]):
        return sorted(glob.glob(args[0]+"/????/??????.png"))
    else:
        return args

class OcropusFileNotFound:
    def __init__(self,fname):
        self.fname = fname
    def __str__(self):
        return "<OcropusFileNotFound "+self.fname+">"

data_paths = [
    ".",
    "./models",
    "./data",
    "./gui",
    "/usr/local/share/ocropus/models",
    "/usr/local/share/ocropus/data",
    "/usr/local/share/ocropus/gui",
    "/usr/local/share/ocropus",
]

def ocropus_find_file(fname):
    """Search for OCRopus-related files in common OCRopus install
    directories (as well as the current directory)."""
    if os.path.exists(fname):
        return fname
    for path in data_paths:
        full = path+"/"+fname
        if os.path.exists(full): return full
    raise OcropusFileNotFound(fname)

def fexists(fname):
    if os.path.exists(fname): return fname
    return None

def gtext(fname):
    """Given a file name, determines the ground truth suffix."""
    g = re.search(r'\.(rseg|cseg)\.([^./]+)\.png$',fname)
    if g:
        return g.group(2)
    g = re.search(r'\.([^./]+)\.(rseg|cseg)\.png$',fname)
    if g:
        return g.group(1)
    g = re.search(r'\.([^./]+)\.(png|costs|fst|txt)$',fname)
    if g:
        return g.group(1)
    return ""

def fvariant(fname,kind,gt=None):
    """Find the file variant corresponding to the given file name.
    Possible fil variants are line (or png), rseg, cseg, fst, costs, and txt.
    Ground truth files have an extra suffix (usually something like "gt",
    as in 010001.gt.txt or 010001.rseg.gt.png).  By default, the variant
    with the same ground truth suffix is produced.  The non-ground-truth
    version can be produced with gt="", the ground truth version can
    be produced with gt="gt" (or some other desired suffix)."""
    if gt is None:
        gt = gtext(fname)
    elif gt!="":
        gt = "."+gt
    base,ext = allsplitext(fname)
    if kind=="line" or kind=="png":
        return base+gt+".png"
    if kind=="rseg":
        return base+".rseg"+gt+".png"
    if kind=="cseg":
        return base+".cseg"+gt+".png"
    if kind=="costs":
        return base+gt+".costs"
    if kind=="fst":
        return base+gt+".fst"
    if kind=="txt":
        return base+gt+".txt"
    raise Exception("unknown kind: %s"%kind)

def fcleanup(fname,gt,kinds):
    for kind in kinds:
        s = fvariant(fname,kind,gt)
        if os.path.exists(s): os.unlink(s)

def ffind(fname,kind,gt=None):
    """Like fvariant, but throws an IOError if the file variant
    doesn't exist."""
    s = fvariant(fname,kind,gt=gt)
    if not os.path.exists(s):
        raise IOError(s)
    return s

def fopen(fname,kind,gt=None,mode="r"):
    """Like fvariant, but opens the file."""
    return open(fvariant(fname,kind,gt),mode)

################################################################
### Utility for setting "parameters" on an object: a list of keywords for
### changing instance variables.
################################################################

def set_params(object,kw,warn=1):
    """Given an object and a dictionary of keyword arguments,
    set only those object properties that are already instance
    variables of the given object.  Returns a new dictionary
    without the key,value pairs that have been used.  If
    all keywords have been used, afterwards, len(kw)==0."""
    kw = kw.copy()
    for k,v in kw.items():
        if hasattr(object,k):
            setattr(object,k,v)
            del kw[k]
    return kw

################################################################
### warning and logging
################################################################

def caller():
    frame = sys._getframe(2)
    info = inspect.getframeinfo(frame)
    result = "%s:%d (%s)"%(info.filename,info.lineno,info.function)
    del frame
    return result

def logging(message,*args):
    """Write a log message (to stderr by default)."""
    message = message%args
    sys.stderr.write(message)

def die(message,*args):
    """Die with an error message."""
    message = message%args
    message = caller()+" FATAL "+message+"\n"
    sys.stderr.write(message)
    sys.exit(1)

def warn(message,*args):
    """Give a warning message."""
    message = message%args
    message = caller()+" WARNING "+message+"\n"
    sys.stderr.write(message)

already_warned = {}

def warn_once(message,*args):
    """Give a warning message, but just once."""
    c = caller()
    if c in already_warned: return
    already_warned[c] = 1
    message = message%args
    message = c+" WARNING "+message+"\n"
    sys.stderr.write(message)

def quick_check_page_components(page_bin,dpi):
    """Quickly check whether the components of page_bin are
    reasonable.  Returns a value between 0 and 1; <0.5 means that
    there is probably something wrong."""
    return 1.0

def quick_check_line_components(line_bin,dpi):
    """Quickly check whether the components of line_bin are
    reasonable.  Returns a value between 0 and 1; <0.5 means that
    there is probably something wrong."""
    return 1.0

def deprecated(func):
    """This is a decorator which can be used to mark functions
    as deprecated. It will result in a warning being emmitted
    when the function is used."""
    def newFunc(*args, **kwargs):
        warnings.warn("Call to deprecated function %s." % func.__name__,
                      category=DeprecationWarning,stacklevel=2)
        return func(*args, **kwargs)
    newFunc.__name__ = func.__name__
    newFunc.__doc__ = func.__doc__
    newFunc.__dict__.update(func.__dict__)
    return newFunc

################################################################
### conversion functions
################################################################

def ustrg2unicode(u,lig=ligatures.lig):
    """Convert an iulib ustrg to a Python unicode string; the
    C++ version iulib.ustrg2unicode does weird things for special
    symbols like -3"""
    result = ""
    for i in range(u.length()):
        value = u.at(i)
        if value>=0:
            c = lig.chr(value)
            if c is not None:
                result += c
            else:
                result += "<%d>"%value
    return result

################################################################
### simple shape comparisons
################################################################

def make_mask(image,r):    
    skeleton = thin(image)
    mask = ~(morphology.binary_dilation(image,iterations=r) - morphology.binary_erosion(image,iterations=r))
    mask |= skeleton # binary_dilation(skeleton,iterations=1)
    return mask

def dist(image,item):
    assert image.shape==item.shape,[image.shape,item.shape]
    ix,iy = measurements.center_of_mass(image)
    if isnan(ix) or isnan(iy): return 9999,9999,None
    # item = (item>amax(item)/2) # in case it's grayscale
    x,y = measurements.center_of_mass(item)
    if isnan(x) or isnan(y): return 9999,9999,None
    dx,dy = int(0.5+x-ix),int(0.5+y-iy)
    shifted = interpolation.shift(image,(dy,dx))
    if abs(dx)>2 or abs(dy)>2:
        return 9999,9999,None
    if 0:
        cla()
        subplot(121); imshow(image-item)
        subplot(122); imshow(shifted-item)
        show()
    image = shifted
    mask = make_mask(image>0.5,1)
    err = sum(mask*abs(item-image))
    total = min(sum(mask*item),sum(mask*image))
    rerr = err/max(1.0,total)
    return err,rerr,image

def symdist(image,item):
    assert type(image)==numpy.ndarray
    assert len(image.shape)==2
    assert len(item.shape)==2
    err,rerr,transformed = dist(image,item)
    err1,rerr1,transformed1 = dist(item,image)
    if rerr<rerr1: return err,rerr,transformed
    else: return err1,rerr1,transformed1

def cut(image,box,margin=0,bg=0,dtype=None):
    (r0,c0,r1,c1) = box
    r0 -= margin; c0 -= margin; r1 += margin; c1 += margin
    if dtype is None: dtype = image.dtype
    result = interpolation.shift(image,(-r0,-c0),output=dtype,order=0,cval=bg)
    return result[:(r1-r0),:(c1-c0)]

### code for instantiation native components

def pyconstruct(s):
    """Constructs a Python object from a constructor, an expression
    of the form x.y.z.name(args).  This ensures that x.y.z is imported.
    In the future, more forms of syntax may be accepted."""
    env = {}
    if "(" not in s:
        s += "()"
    path = s[:s.find("(")]
    if "." in path:
        module = path[:path.rfind(".")]
        print "import",module
        exec "import "+module in env
    return eval(s,env)

def mkpython(name):
    """Tries to instantiate a Python class.  Gives an error if it looks
    like a Python class but can't be instantiated.  Returns None if it
    doesn't look like a Python class."""
    if type(name) is not str:
        return name()
    elif name[0]=="=":
        return pyconstruct(name[1:])
    elif "(" in name or "." in name:
        return pyconstruct(name)
    else:
        return None

def make_ICleanupGray(name):
    """Make a native component or a Python component.  Anything containing
    a "(" is assumed to be a Python component."""
    return mkpython(name) or CleanupGray().make(name)
def make_ICleanupBinary(name):
    """Make a native component or a Python component.  Anything containing
    a "(" is assumed to be a Python component."""
    return mkpython(name) or CleanupBinary().make(name)
def make_IBinarize(name):
    """Make a native component or a Python component.  Anything containing
    a "(" is assumed to be a Python component."""
    return mkpython(name) or Binarize().make(name)
def make_ITextImageClassification(name):
    """Make a native component or a Python component.  Anything containing
    a "(" is assumed to be a Python component."""
    return mkpython(name) or TextImageClassification().make(name)
def make_ISegmentPage(name):
    """Make a native component or a Python component.  Anything containing
    a "(" is assumed to be a Python component."""
    return mkpython(name) or SegmentPage().make(name)
def make_ISegmentLine(name):
    """Make a native component or a Python component.  Anything containing
    a "(" is assumed to be a Python component."""
    return mkpython(name) or SegmentLine().make(name)
def make_IGrouper(name):
    """Make a native component or a Python component.  Anything containing
    a "(" is assumed to be a Python component."""
    return mkpython(name) or Grouper().make(name)
def make_IRecognizeLine(name):
    """Make a native component or a Python component.  Anything containing
    a "(" is assumed to be a Python component."""
    return mkpython(name) or RecognizeLine().make(name)
def make_IModel(name):
    """Make a native component or a Python component.  Anything containing
    a "(" is assumed to be a Python component."""
    return mkpython(name) or Model().make(name)
def make_IExtractor(name):
    """Make a native component or a Python component.  Anything containing
    a "(" is assumed to be a Python component."""
    return mkpython(name) or Extractor().make(name)

################################################################
### alignment, segmentations, and conversions
################################################################

def intarray_as_unicode(a,skip0=1):
    result = u""
    for i in range(len(a)):
        if a[i]!=0:
            assert a[i]>=0 and a[i]<0x110000,"%d (0x%x) character out of range"%(a[i],a[i])
            result += unichr(a[i])
    return result
    
def read_lmodel_or_textlines(file):
    """Either reads a language model in .fst format, or reads a text file
    and corresponds a language model out of its lines."""
    if not os.path.exists(file): raise IOError(file)
    if file[-4:]==".fst":
        return ocrofst.OcroFST().load(file)
    else:
        import fstutils
        result = fstutils.load_text_file_as_fst(file)
        assert isinstance(result,ocrofst.OcroFST)
        return result

def OLD_rseg_map(inputs):
    """This takes an array of the input labels produced by a beam search.
    The input labels contain the correspondence
    between the rseg label and the character.  These are put into
    a dictionary and returned.  This is used for alignment between
    a segmentation and text."""
    n = len(inputs)
    segs = []
    for i in range(n):
        start = inputs[i]>>16
        end = inputs[i]&0xffff
        segs.append((start,end))
    n = amax([s[1] for s in segs])+1
    count = 0
    map = zeros(n,'i')
    for i in range(len(segs)):
        start,end = segs[i]
        if start==0 or end==0: continue
        count += 1
        for j in range(start,end+1):
            map[j] = count
    return map

def OLD_recognize_and_align(image,linerec,lmodel,beam=1000,nocseg=0):
    """Perform line recognition with the given line recognizer and
    language model.  Outputs an object containing the result (as a
    Python string), the costs, the rseg, the cseg, the lattice and the
    total cost.  The recognition lattice needs to have rseg's segment
    numbers as inputs (pairs of 16 bit numbers); SimpleGrouper
    produces such lattices.  cseg==None means that the connected
    component renumbering failed for some reason."""

    assert isinstance(linerec,RecognizeLine)

    lattice,rseg = linerec.recognizeLineSeg(image)
    v1,v2,ins,outs,costs = beam_search(lattice,lmodel,beam)
    result = intarray_as_unicode(outs,skip0=0)

    # compute the cseg
    rmap = rseg_map(ins)
    n = len(rseg)
    if not nocseg and len(rmap)>1:
        r,c = rseg.shape
        cseg = zeros((r,c),'i')
        for i in range(r):
            for j in range(c):
                value = rseg[i,j]
                cseg[i,j] = rmap[value]
    else:
        cseg = None

    # return everything we computed
    return utils.Record(image=image,
                        output=result,
                        raw=outs,
                        costs=costs,
                        rseg=rseg,
                        cseg=cseg,
                        lattice=lattice,
                        cost=sum(costs))

def rect_union(rectangles):
    if len(rectangles)<1: return (0,0,-1,-1)
    r = array(rectangles)
    return (amin(r[:,0]),amax(r[:,0]),amin(r[:,1]),amax(r[:1]))

def compute_alignment(lattice,rseg,lmodel,beam=1000,verbose=0,lig=ligatures.lig):
    """Given a lattice produced by a recognizer, a raw segmentation,
    and a language model, computes the best solution, the cseg, and
    the corresponding costs.  These are returned as Python data structures.
    The recognition lattice needs to have rseg's segment numbers as inputs
    (pairs of 16 bit numbers); SimpleGrouper produces such lattices."""

    v1,v2,ins,outs,costs = beam_search(lattice,lmodel,beam)

    # useful for debugging

    if 0:
        for i in range(len(ins)):
            print i,ins[i]>>16,ins[i]&0xffff,lig.chr(outs[i]),costs[i]

    assert len(ins)==len(outs)
    n = len(ins)

    # This is a little tricky because we need to deal with ligatures.
    # For any transition followed by epsilon transitions on the
    # output, we group all the segments of the epsilon transition with
    # the preceding non-epsilon transition.

    result_l = [""]
    costs_l = [0.0]
    segs = [(-1,-1)]

    i = 0
    while i<n:
        j = i+1
        start = ins[i]>>16
        end = ins[i]&0xffff
        cls = [outs[i]]
        # print "  %4d (%2d,%2d) %3d %s"%(i,start,end,outs[i],unichr(outs[i]))
        # while j<n and ((ins[j]==0 and outs[j]!=32) or outs[j]==0):
        while j<n and outs[j]==0:
            # print " +%4d (%2d,%2d) %3d %s"%(i,ins[j]>>16,ins[j]&0xffff,outs[j],unichr(outs[j]))
            if ins[j]!=0:
                start = min(start,ins[j]>>16)
                end = max(end,ins[j]&0xffff)
            if outs[j]!=0:
                cls.append(outs[j])
            j = j+1
        cls = "".join([lig.chr(x) for x in cls])
        if cls!="":
            result_l.append(cls)
            costs_l.append(sum(costs[i:j]))
            segs.append((start,end))
        i = j

    rseg_boxes = docproc.seg_boxes(rseg)

    # Now run through the segments and create a table that maps rseg
    # labels to the corresponding output element.

    assert len(result_l)==len(segs)
    assert len(costs_l)==len(segs)
    bboxes = []

    rmap = zeros(amax(rseg)+1,'i')
    for i in range(1,len(segs)):
        start,end = segs[i]
        if verbose: print i+1,start,end,"'%s'"%result[i],costs.at(i)
        if start==0 or end==0: continue
        rmap[start:end+1] = i
        bboxes.append(rect_union(rseg_boxes[start:end+1]))
    assert rmap[0]==0

    # Finally, to get the cseg, apply the rmap table from above.

    cseg = zeros(rseg.shape,'i')
    for i in range(cseg.shape[0]):
        for j in range(cseg.shape[1]):
            cseg[i,j] = rmap[rseg[i,j]]

    if 0:
        print len(rmap),rmap
        print len(segs),segs
        print len(result_l),result_l
        print len(costs_l),costs_l
        print amin(cseg),amax(cseg)

    # assert len(segs)==len(rmap) 
    assert len(segs)==len(result_l) 
    assert len(segs)==len(costs_l)
    return utils.Record(
        # alignment output; these all have the same lengths
        output_l=result_l,
        segs=segs,
        costs=array(costs_l,'f'),
        # other convenient output representation
        output="".join(result_l),
        output_t=fstutils.implode_transcription(result_l),
        cost=sum(costs_l),
        # raw beam search output
        ins=ins,
        outs=outs,
        # segmentation images
        rseg=rseg,
        cseg=cseg,
        # the lattice
        lattice=lattice,
        # bounding boxes
        bboxes=bboxes,
        )

def recognize_and_align(image,linerec,lmodel,beam=1000,nocseg=0,lig=ligatures.lig):
    """Perform line recognition with the given line recognizer and
    language model.  Outputs an object containing the result (as a
    Python string), the costs, the rseg, the cseg, the lattice and the
    total cost.  The recognition lattice needs to have rseg's segment
    numbers as inputs (pairs of 16 bit numbers); SimpleGrouper
    produces such lattices.  cseg==None means that the connected
    component renumbering failed for some reason."""

    lattice,rseg = linerec.recognizeLineSeg(image)
    v1,v2,ins,outs,costs = beam_search(lattice,lmodel,beam)
    result = compute_alignment(lattice,rseg,lmodel,beam=beam,lig=lig)
    return result

################################################################
### loading and saving components
################################################################

# This code has to deal with a lot of special cases for all the
# different formats we have accrued.

def obinfo(ob):
    result = str(ob)
    if hasattr(ob,"shape"): 
        result += " "
        result += str(ob.shape)
    return result

def save_component(file,object,verbose=0,verify=0):
    """Save an object to disk in an appropriate format.  If the object
    is a wrapper for a native component (=inherits from
    CommonComponent and has a comp attribute, or is in package
    ocropus), write it using ocropus.save_component in native format.
    Otherwise, write it using Python's pickle.  We could use pickle
    for everything (since the native components pickle), but that
    would be slower and more confusing."""
    if hasattr(object,"save_component"):
        object.save_component(file)
        return
    # FIXME -- get rid of this eventually
    if isinstance(object,ocroold.CommonComponent) and hasattr(object,"comp"):
        import ocropus
        ocropus.save_component(file,object.comp)
        return
    if type(object).__module__=="ocropus":
        import ocropus
        ocropus.save_component(file,object)
        return
    if verbose: 
        print "[save_component]"
    if verbose:
        for k,v in object.__dict__.items():
            print ":",k,obinfo(v)
    with open(file,"wb") as stream:
        pickle.dump(object,stream,pickle_mode)
    if verify:
        if verbose: 
            print "[trying to read it again]"
        with open(file,"rb") as stream:
            test = pickle.load(stream)

def load_component(file):
    """Load a component from disk.  If file starts with "@", it is
    taken as a Python expression and evaluated, but this can be overridden
    by starting file with "=".  Otherwise, the contents of the file are
    examined.  If it looks like a native component, it is loaded as a line
    recognizers if it can be identified as such, otherwise it is loaded
    with load_Imodel as a model.  Anything else is loaded with Python's
    pickle.load."""

    if file[0]=="=":
        return pyconstruct(file[1:])
    elif file[0]=="@":
        file = file[1:]
    # FIXME -- get rid of this eventually
    with open(file,"r") as stream:
        start = stream.read(128)
    # FIXME -- get rid of this eventually
    if start.startswith("<object>\nlinerec\n"):
        warnings.warn("loading old-style linerec: %s"%file)
        result = RecognizeLine()
        import ocropus
        result.comp = ocropus.load_IRecognizeLine(file)
        return result
    # FIXME -- get rid of this eventually
    if start.startswith("<object>"):
        warnings.warn("loading old-style cmodel: %s"%file)
        result = ocroold.Model()
        import ocropus
        result.comp = ocropus.load_IModel(file)
        return result
    with open(file,"rb") as stream:
        return pickle.load(stream)

def load_linerec(file,wrapper=None):
    if wrapper is None:
        wrapper=segrec.CmodelLineRecognizer
    component = load_component(file)
    if hasattr(component,"recognizeLine"):
        return component
    if hasattr(component,"coutputs"):
        return wrapper(cmodel=component)
    raise Exception("wanted linerec, got %s"%component)

def binarize_range(image,dtype='B'):
    threshold = (amax(image)+amin(image))/2
    scale = 1
    if dtype=='B': scale = 255
    return array(scale*(image>threshold),dtype=dtype)

def simple_classify(model,inputs):
    result = []
    for i in range(len(inputs)):
        result.append(model.coutputs(inputs[i]))
    return result

