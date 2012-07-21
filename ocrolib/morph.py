################################################################
### various add-ons to the SciPy morphology package
################################################################

from numpy import *
import pylab
from scipy.ndimage import morphology,measurements
from scipy.ndimage.morphology import *

def label(image,**kw):
    """Redefine the scipy.ndimage.measurements.label function to
    work with a wider range of data types.  The default function
    is inconsistent about the data types it accepts on different
    platforms."""
    try: return measurements.label(image,**kw)
    except: pass
    types = ["int32","uint32","int64","unit64","int16","uint16"]
    for t in types:
	try: return measurements.label(array(image,dtype=t),**kw) 
	except: pass
    # let it raise the same exception as before
    return measurements.label(image,**kw)

def find_objects(image,**kw):
    """Redefine the scipy.ndimage.measurements.find_objects function to
    work with a wider range of data types.  The default function
    is inconsistent about the data types it accepts on different
    platforms."""
    try: return measurements.find_objects(image,**kw)
    except: pass
    types = ["int32","uint32","int64","unit64","int16","uint16"]
    for t in types:
	try: return measurements.find_objects(array(image,dtype=t),**kw) 
	except: pass
    # let it raise the same exception as before
    return measurements.find_objects(image,**kw)
    
def check_binary(image):
    assert image.dtype=='B' or image.dtype=='i' or image.dtype==dtype('bool'),\
        "array should be binary, is %s %s"%(image.dtype,image.shape)
    assert amin(image)>=0 and amax(image)<=1,\
        "array should be binary, has values %g to %g"%(amin(image),amax(image))

def r_dilation(image,size,origin=0):
    check_binary(image)
    return filters.maximum_filter(image,size,origin=origin)

def r_erosion(image,size,origin=0):
    check_binary(image)
    return filters.minimum_filter(image,size,origin=origin)

def r_opening(image,size,origin=0):
    check_binary(image)
    image = r_erosion(image,size,origin=origin)
    return r_dilation(image,size,origin=origin)

def r_closing(image,size,origin=0):
    check_binary(image)
    image = r_dilation(image,size,origin=0)
    return r_erosion(image,size,origin=0)

def rb_dilation(image,size,origin=0):
    output = zeros(image.shape,'f')
    filters.uniform_filter(image,size,output=output,origin=origin,mode='constant',cval=0)
    return (output>0)

def rb_erosion(image,size,origin=0):
    output = zeros(image.shape,'f')
    filters.uniform_filter(image,size,output=output,origin=origin,mode='constant',cval=1)
    return (output==1)

def rb_opening(image,size,origin=0):
    check_binary(image)
    image = rb_erosion(image,size,origin=origin)
    return rb_dilation(image,size,origin=origin)

def rb_closing(image,size,origin=0):
    check_binary(image)
    image = rb_dilation(image,size,origin=origin)
    return rb_erosion(image,size,origin=origin)

def rg_dilation(image,size,origin=0):
    return filters.maximum_filter(image,size,origin=origin)

def rg_erosion(image,size,origin=0):
    return filters.minimum_filter(image,size,origin=origin)

def rg_opening(image,size,origin=0):
    image = r_erosion(image,size,origin=origin)
    return r_dilation(image,size,origin=origin)

def rg_closing(image,size,origin=0):
    image = r_dilation(image,size,origin=0)
    return r_erosion(image,size,origin=0)

def showlabels(x,n=7):
    pylab.imshow(where(x>0,x%7+1,0),cmap=pylab.cm.gist_stern)

def spread_labels(labels,maxdist=9999999):
    """Spread the given labels to the background"""
    distances,features = morphology.distance_transform_edt(labels==0,return_distances=1,return_indices=1)
    indexes = features[0]*labels.shape[1]+features[1]
    spread = labels.ravel()[indexes.ravel()].reshape(*labels.shape)
    spread *= (distances<maxdist)
    return spread

def keep_marked(image,markers):
    """Given a marker image, keep only the connected components
    that overlap the markers."""
    labels,_ = label(image)
    marked = unique(labels*(markers!=0))
    kept = in1d(labels.ravel(),marked)
    return (image!=0)*kept.reshape(*labels.shape)

def remove_marked(image,markers):
    """Given a marker image, remove all the connected components
    that overlap markers."""
    marked = keep_marked(image,markers)
    return image*(marked==0)

def correspondences(labels1,labels2):
    """Given two labeled images, compute an array giving the correspondences
    between labels in the two images."""
    q = 100000
    assert amin(labels1)>=0 and amin(labels2)>=0
    assert amax(labels2)<q
    combo = labels1*q+labels2
    result = unique(combo)
    result = array([result//q,result%q])
    return result

def propagate_labels_simple(regions,labels):
    """Spread the labels to the corresponding regions."""
    rlabels,_ = common.label(regions)
    cors = correspondences(rlabels,labels)
    outputs = zeros(amax(rlabels)+1,'i')
    for o,i in cors.T: outputs[o] = i
    outputs[0] = 0
    return outputs[rlabels]

def propagate_labels(image,labels,conflict=0):
    """Given an image and a set of labels, apply the labels
    to all the regions in the image that overlap a label.
    Assign the value `conflict` to any labels that have a conflict."""
    rlabels,_ = common.label(image)
    cors = correspondences(rlabels,labels)
    outputs = zeros(amax(rlabels)+1,'i')
    oops = -(1<<30)
    for o,i in cors.T:
        if outputs[o]!=0: outputs[o] = oops
        else: outputs[o] = i
    outputs[outputs==oops] = conflict
    outputs[0] = 0
    return outputs[rlabels]

def select_regions(binary,f,min=0,nbest=100000):
    """Given a scoring function f over slice tuples (as returned by
    find_objects), keeps at most nbest regions whose scores is higher
    than min."""
    labels,n = common.label(binary)
    objects = common.find_objects(labels)
    scores = [f(o) for o in objects]
    best = argsort(scores)
    keep = zeros(len(objects)+1,'B')
    for i in best[-nbest:]:
        if scores[i]<=min: continue
        keep[i+1] = 1
    return keep[labels]

def all_neighbors(image):
    """Given an image with labels, find all pairs of labels
    that are directly neighboring each other."""
    q = 100000
    assert amax(image)<q
    assert amin(image)>=0
    u = unique(q*image+roll(image,1,0))
    d = unique(q*image+roll(image,-1,0))
    l = unique(q*image+roll(image,1,1))
    r = unique(q*image+roll(image,-1,1))
    all = unique(r_[u,d,l,r])
    all = c_[all//q,all%q]
    all = unique(array([sorted(x) for x in all]))
    return all

################################################################
### Iterate through the regions of a color image.
################################################################

def renumber_labels_ordered(a,correspondence=0):
    """Renumber the labels of the input array in numerical order so
    that they are arranged from 1...N"""
    assert amin(a)>=0
    assert amax(a)<=2**25
    labels = sorted(unique(ravel(a)))
    renum = zeros(amax(labels)+1,dtype='i')
    renum[labels] = arange(len(labels),dtype='i')
    if correspondence:
        return renum[a],labels
    else:
        return renum[a]

def renumber_labels(a):
    """Alias for renumber_labels_ordered"""
    return renumber_labels_ordered(a)

def pyargsort(seq,cmp=cmp,key=lambda x:x):
    """Like numpy's argsort, but using the builtin Python sorting
    function.  Takes an optional cmp."""
    return sorted(range(len(seq)),key=lambda x:key(seq.__getitem__(x)),cmp=cmp)

def renumber_by_xcenter(seg):
    objects = [(slice(0,0),slice(0,0))]+find_objects(seg)
    def xc(o): return mean((o[1].start,o[1].stop))
    xs = array([xc(o) for o in objects])
    order = argsort(xs)
    segmap = zeros(amax(seg)+1,'i')
    for i,j in enumerate(order): segmap[j] = i
    return segmap[seg]

