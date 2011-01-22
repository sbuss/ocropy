from scipy import stats
from scipy.ndimage import measurements

from common import *

def avg(*args):
    return mean(args)

def seg_boxes(seg,math=0):
    """Given a color segmentation, return a list of bounding boxes.
    Bounding boxes are returned as tuples (y0,y1,x0,x1).  With
    math=0, raster coordinates are used, with math=1, Postscript
    coordinates are used (however, the order of the values in the
    tuple doesn't change)."""
    seg = array(seg,'uint32')
    slices = measurements.find_objects(seg)
    h = seg.shape[0]
    result = []
    for i in range(len(slices)):
        if slices[i] is None: continue
        (ys,xs) = slices[i]
        if math:
            result += [(h-ys.stop-1,h-ys.start-1,xs.start,xs.stop)]
        else:
            result += [(ys.start,ys.stop,xs.start,xs.stop)]
    return result

def seg_geometry(segmentation):
    """Given a line segmentation (either an rseg--preferably connected
    component based--or a cseg, return (mh,a,b), where mh is the
    medium component height, and y=a*x+b is a line equation (in
    Postscript coordinates) for the center of the text line.  This
    function is used as a simple, standard estimator of text line
    geometry.  The intended use is to encode the size and centers of
    bounding boxes relative to these estimates and add these as
    features to the input of a character classifier, allowing it to
    distinguish otherwise ambiguous pairs like ,/' and o/O."""
    boxes = seg_boxes(segmentation,math=1)
    heights = [(y1-y0) for (y0,y1,x0,x1) in boxes]
    mh = stats.scoreatpercentile(heights,per=40)
    centers = [(avg(y0,y1),avg(x0,x1)) for (y0,y1,x0,x1) in boxes]
    xs = [x for y,x in centers]
    ys = [y for y,x in centers]
    a,b = polyfit(xs,ys,1)
    return mh,a,b

def rel_char_geom(box,params):
    """Given a character bounding box and a set of line geometry parameters,
    compute relative character position and size."""
    y0,y1,x0,x1 = box
    mh,a,b = params
    y = avg(y0,y1)
    x = avg(x0,x1)
    yl = a*x+b
    rel_ypos = (y-yl)/mh
    rel_width = (x1-x0)*1.0/mh
    rel_height = (y1-y0)*1.0/mh
    return rel_ypos,rel_width,rel_height

def rel_geo_normalize(rel):
    if type(rel)==str:
        rel = [float(x) for x in rel.split()]
    ry,rw,rh = rel
    ry = clip(2*ry,-1,1)
    rw = clip(log(rw),-1,1)
    rh = clip(log(rh),-1,1)
    geometry = array([ry,rw,rh],'f')
    return geometry

