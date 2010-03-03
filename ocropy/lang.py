import sys,os,re,glob,math,glob,signal
import iulib,ocropus
from pylab import amax,zeros

### commonly confused characters in OCR

ocr_confusions_list = [
    ["c","C"],
    ["l","1","I","|","/"],
    ["o","O","0"],
    ["s","S"],
    ["u","U"],
    ["v","V"],
    ["w","W"],
    ["x","X"],
    ["z","Z"],
    [",","'",".","`"],
]

ocr_confusions = {}

for e in ocr_confusions_list:
    for i in range(len(e)):
        ocr_confusions[e[i]] = e

