import os,os.path,re,numpy,unicodedata,sys,warnings,inspect,glob,traceback,string
import numpy
from numpy import *
from scipy.misc import imsave
from scipy.ndimage import interpolation,measurements,morphology
import common
import ocrofst
import sl
from pycomp import PyComponent
from collections import Counter
import ligatures

class Grouper(PyComponent):
    """Perform grouping operations on segmented text lines, and
    create a finite state transducer for classification results."""
    def __init__(self,**kw):
        self.maxrange = 4
        self.maxdist = 2
        self.maxaspect = 2.5
        self.maxwidth = 2.5
        self.fullheight = 0
        self.pre2seg = None
        self.lig = ligatures.lig
    def setSegmentation(self,segmentation,cseg=0,preferred=None):
        """Set the line segmentation."""
        # reorder the labels by the x center of bounding box
        segmentation = common.renumber_labels_by_boxes(segmentation,key=lambda x:mean((x[1].start,x[1].stop)))
        if preferred is not None:
            preferred = common.renumber_labels_by_boxes(preferred,key=lambda x:mean((x[1].start,x[1].stop)))
            assert amax(segmentation)<32000 and amax(preferred)<32000
            combined = ((preferred<<16)|segmentation)
            correspondences = [(k>>16,k&0xffff) for k,v in Counter(combined.ravel()).most_common() if v>5]
            # print sorted(correspondences)
            self.pre2seg = correspondences
        # compute the bounding boxes in order
        boxes = [None]+measurements.find_objects(segmentation)
        n = len(boxes)
        # now consider groups of boxes
        groups = []
        for i in range(1,n):
            for r in range(1,self.maxrange+1):
                box = None
                gap = 0
                labels = []
                for j in range(i,min(n,i+r)):
                    if box is not None:
                        gap = max(gap,boxes[j][1].start-box[1].stop)
                    box = sl.union(box,boxes[j])
                    labels.append(j)
                if r>1:
                    # skip if we didn't get enough components
                    if len(labels)!=r: continue
                    # skip if two constituent boxes have too large a gap between them
                    if gap>self.maxdist: continue
                    a = sl.aspect(box)
                    # skip if the aspect ratio is wrong
                    if 1.0/a>self.maxaspect: continue
                    # print "@",i,j,box,labels
                groups.append((box,labels))
        # compute some statistics
        mw = median([sl.dim0(g[0]) for g in groups])
        # eliminate compound boxes that are too wide
        groups = [g for g in groups if len(g[1])==1 or sl.dim1(g[0])<self.maxwidth*mw]
        # now we have a list of candidate groups
        self.segmentation = segmentation
        self.groups = groups
        self.clearLattice()
        return len(self.groups)
    def setCSegmentation(self,segmentation):
        """Set the line segmentation, assumed to be a cseg.  This returns exactly and only
        the groups corresponding to each labeled object.  Objects should be labeled
        consecutively."""
        # compute the bounding boxes in order
        boxes = [None] + measurements.find_objects(segmentation)
        n = len(boxes)
        # now consider groups of boxes
        groups = []
        for i in range(1,n):
            box = boxes[i]
            labels = [i]
            groups.append((box,labels))
        self.segmentation = segmentation
        self.groups = groups
        self.clearLattice()
        return len(self.groups)
    def clearLattice(self):
        n = len(self.groups)
        self.costs = [[] for i in range(n)]
        self.space_costs = ones((n,2))*999999.0
    def length(self):
        """Number of groups."""
        return len(self.groups)
    def getMask(self,i,margin=0):
        """Get the mask image for group i."""
        box,labels = self.groups[i]
        if sl.empty(box): return None
        mask = sl.cut(self.segmentation,box,margin=margin)
        shape = mask.shape
        mask = in1d(mask,array(labels,'i'))
        mask.shape = shape
        return mask
    def getMaskAt(self,i,rect):
        """Get the mask for group i and contained in the given rectangle."""
        raise Exception("unimplemented")
    def isEmpty(self,i):
        return sl.empty(self.groups[i][0])
    def boundingBox(self,i):
        """Get the bounding box for group i."""
        box = self.groups[i][0]
        r0,r1,c0,c1 = sl.raster(box)
        return (r0,c0,r1,c1)
    def bboxMath(self,i):
        """Get the bounding box for group i."""
        return sl.math(self.groups[i][0],h=self.segmentation.shape[0])
    def start(self,i):
        """Get the identifier of the character segment starting this group."""
        return amin(self.groups[i][1])
    def end(self,i):
        """Get the identifier of the character segment ending this group."""
        return amax(self.groups[i][1])
    def getSegments(self,i):
        """Get a list of all the segments making up this group."""
        return self.groups[i][1]
    def isCombined(self,i):
        if self.pre2seg is None: return False
        # get the set of segments
        s = self.getSegments(i)
        # find all the preferred segments corresponding to this one
        p = set([x for x,y in self.pre2seg if y in s])
        # print i,sorted(list(p))
        # does it combine several "preferred" segments
        combined = (len(p)>=2)
        return combined
    def isSplit(self,i):
        if self.pre2seg is None: return False
        # get the set of segments
        s = self.getSegments(i)
        # find all the preferred segments corresponding to this one
        p = set([x for x,y in self.pre2seg if y in s])
        if len(p)>1: return False
        # find all the regular segments corresponding to the preferred one
        r = set([y for x,y in self.pre2seg if x in p])
        # print "---",i,":",set(s),r
        return set(s)!=r
    def extractWithBackground(self,source,dflt,i,grow=0,dtype=None):
        """Extract the image corresponding to group i.  Background pixels are
        filled in with dflt."""
        if dtype is None: dtype = source.dtype
        if self.isEmpty(i): return None
        image = sl.cut(source,self.boundingBox(i),margin=grow,bg=dflt,dtype=dtype)
        return image
    def extractWithMask(self,source,i,grow=0,bg=0,margin=None,dtype=None):
        """Extract the image and mask corresponding to group i"""
        if dtype is None: dtype = source.dtype
        if self.isEmpty(i): return None
        if margin is None: margin=grow
        box,labels = self.groups[i]
        image = sl.cut(source,box,margin=margin,bg=bg,dtype=dtype)
        mask = sl.cut(self.segmentation,box,margin=grow)
        mask = 0+in1d(mask.ravel(),array(labels,'i')).reshape(image.shape)
        if grow>0: mask = morphology.binary_dilation(mask,iterations=grow)
        return where(mask,image,bg),mask
    def extractSliced(self,source,dflt,i,grow=0):
        """Extract the image and mask corresponding to group i, slicing through the entire input
        line.  Background pixels are filled with dflt."""
        raise Exception("unimplemented")
    def extractSlicedWithMask(self,source,i,grow=0):
        """Extract the image and mask corresponding to group i, slicing through the entire input
        line.  Background pixels are filled with dflt."""
        raise Exception("unimplemented")
    def setClass(self,i,cls,cost):
        """Set the class for group i, and the associated cost.  The class may
        be given as an integer, as a string, or as a unicode string.  The cost
        should be non-negative."""
        # print "...",i,cls,cost,type(cls)
        if type(cls)==int:
            if cls<256:
                cls = chr(cls)
            elif cls<0x110000:
                cls = unichr(cls)
            else:
                raise Exception("class out of range: %s (%s)"%(cls,hex(cls)))
        assert type(cls)==str or type(cls)==unicode
        self.costs[i].append((cost,cls))
    def setSpaceCost(self,i,yes_cost,no_cost):
        """Set the cost of putting a space or not putting a space after
        group i."""
        self.space_costs[i] = (yes_cost,no_cost)
    def saveLattice(self,stream):
        """Write the lattice in a simple text format."""
        for i in range(len(self.groups)):
            box,segs = self.groups[i]
            start = amin(segs)
            end = amax(segs)
            sid = (start<<16)+end
            yes = self.space_costs[i][0]
            no = self.space_costs[i][1]
            if yes>9999.0 and no>9999.0: no = 0.0
            stream.write("segment %d\t%d:%d\t%d:%d:%d:%d\t%.4f %.4f\n"%
                         (i,start,end,box[1].start,box[0].start,box[1].stop,box[0].stop,yes,no))
            for j in range(len(self.costs[i])):
                cost,cls = self.costs[i][j]
                stream.write("chr %d\t%4d\t%.4f\t%s\n"%(i,j,cost,cls))
    def loadLattice(self,stream,segmentation=None):
        self.segmentation = segmentation
        self.groups = []
        self.costs = []
        self.space_costs = []
        for lineno,line in enumerate(stream.readlines()):
            f = line[:-1].split()
            if f[0]=="segment":
                i = int(f[1])
                assert i==len(self.groups),"bad input format ('segment' out of order), line %d"%lineno
                start,end = [int(x) for x in f[2].split(":")]
                (x0,y0,x1,y1) = [int(x) for x in f[3].split(":")]
                box = (slice(y0,y1),slice(x0,x1))
                yes,no = [float(x) for x in f[4:6]]
                self.groups.append((box,range(start,end+1)))
                self.space_costs.append((yes,no))
                self.costs.append([])
            elif f[0]=="chr":
                i = int(f[1])
                j = int(f[2])
                assert i==len(self.groups)-1,"bad input format ('segment' out of order), line %d"%lineno
                assert j==len(self.costs[i]),"bad input format ('chr' out of order), line %d"%lineno
                cost = float(f[3])
                cls = f[4]
                self.costs[i].append((cost,cls))
            elif f[0]=="#":
                pass
            else:
                raise Error("bad input format")
    def getLatticeAsFST(self,fst=None):
        """Construct the lattice for the group, using the setClass and setSpaceCost information."""
        if fst is None:
            fst = ocrofst.OcroFST()
        final = max([amax(segs) for (box,segs) in self.groups])+1
        if self.segmentation is not None:
            assert final==amax(self.segmentation)+1
        states = [-1]+[fst.newState() for i in range(1,final+1)]
        fst.setStart(states[1])
        fst.setAccept(states[final])
        for i in range(len(self.groups)):
            box,segs = self.groups[i]
            start = amin(segs)
            end = amax(segs)
            sid = (start<<16)+end
            yes = self.space_costs[i][0]
            no = self.space_costs[i][1]
            if yes>9999.0 and no>9999.0: no = 0.0
            for j in range(len(self.costs[i])):
                cost,cls = self.costs[i][j]
                n = len(cls)
                state = states[start]
                for k in range(n):
                    c = ord(cls[k])
                    next = -1
                    if k<n-1:
                        next = fst.newState()
                        states.append(next)
                    else:
                        next = states[end+1]
                    ccost = 0.0
                    if k==0: ccost += cost
                    if k==n-1: ccost += no
                    if ccost<1000.0:
                        fst.addTransition(state,next,c,float(ccost),int(sid))
                    if k==n-1 and yes<1000.0:
                        ccost = cost if k==0 else 0.0
                        space_state = fst.newState()
                        states.append(space_state)
                        fst.addTransition(state,space_state,c,float(ccost),int(sid))
                        fst.addTransition(space_state,next,32,float(yes),0)
                    state = next
        return fst
    def getLatticeLigAsFST(self,fst=None):
        """Construct the lattice for the group, using the setClass and setSpaceCost information."""
        lig = self.lig
        if fst is None:
            fst = ocrofst.OcroFST()
        final = amax(self.segmentation)+1
        states = [-1]+[fst.newState() for i in range(1,final+1)]
        fst.setStart(states[1])
        fst.setAccept(states[final])
        for i in range(len(self.groups)):
            box,segs = self.groups[i]
            start = amin(segs)
            end = amax(segs)
            sid = (start<<16)+end
            yes = self.space_costs[i][0]
            no = self.space_costs[i][1]
            if yes>9999.0 and no>9999.0: no = 0.0
            for j in range(len(self.costs[i])):
                cost,cls = self.costs[i][j]
                state = states[start]
                next = states[end+1]
                c = lig.ord(cls)
                if c is None or c<0:
                    raise common.RecognitionError("unknown output ligature: %s"%cls)
                # no space
                ccost = cost + no
                if ccost<1000.0:
                    fst.addTransition(state,next,c,float(ccost),int(sid))
                # yes space
                ccost = cost + yes
                if ccost<1000.0:
                    space_state = fst.newState()
                    states.append(space_state)
                    # split the cost between classification and space between the two transition
                    fst.addTransition(state,space_state,c,float(cost),int(sid))
                    fst.addTransition(space_state,next,32,yes,0)
                state = next
        return fst
    def getLattice(self):
        ### DEPRECATED
        return self.getLatticeAsFST()
    def getLatticeLig(self):
        ### DEPRECATED
        return self.getLatticeLigAsFST()
    def pixelSpace(self,i):
        raise Exception("unimplemented")
    def setSegmentationAndGt(self,rseg,cseg,gt):
        self.setSegmentation(rseg)
        temp = unique(rseg*10000+cseg)
        cs = temp%10000
        rs = temp//10000
        raise Exception("unimplemented")
    def getGtIndex(self,i):
        raise Exception("unimplemented")
    def getGtClass(self,i):
        raise Exception("unimplemented")
