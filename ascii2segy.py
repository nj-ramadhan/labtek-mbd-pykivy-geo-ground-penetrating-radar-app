# -*- coding: utf-8 -*-
"""ascii2segy

This script uses segpy-rewrite to convert velf ascii files to segy files. 
Please use 64 bit python for large files as data is loaded into memory.

Run with -h to get more information on parameters.

Outputs
-------
A segy file containing the velocities from the input ascii file.

Inputs
-------
Example input file format:
```
###############################################################################
#BEGIN HEADER
#X
#Y
#Z (time)
#FLOAT  "Stacking Velocity"
#FLOAT  "XLINE"
#FLOAT  "INLINE"
#END HEADER
   7618446.0	  141544.0	       0.0	    1510.0	 10040.0	2060	
   7618446.0	  141544.0	      40.0	    1510.0	 10040.0	2060
   7618446.0	  141544.0	      80.0	    1510.0	 10040.0	2060
```
Examples
--------
ascii2segy.py test.csv -o test.sgy
ascii2segy.py -h
ascii2segy.py test.csv -s 40 -m 5000 -c 15 -n 4 -d 2 -v 3 -e 1


Installation
-------
Make sure you have 64bit python 3.3 installation
Install the requirements listed in requirements.txt. Note that this uses 
segpy 2.0.0a2 from github.com/rob-smallshire/segpy which you can install using 
the command below: 
```
pip install git+git://github.com/sixty-north/segpy/tree/91562fddfd6d8424ee4161f4417982243512c150
```
In a command propmt with python64 3.3 install and test:
```
pip install -r requirements.txt
python ascii2segy.py ./test_data/test_input.tsv
```

License
------
This inherits it's license from segpy

More Info
-------
Created on Mon Aug 04 09:11:11 2014

Planned changes
------
Try this on a large range of data
Unit tests
Refactor for file larger than memory by reading and writing iterativly from a 
    hard disc caches file.

@version 0.27


"""

import os
import sys
import argparse
import numpy as np
import datetime
import pylab
from pylab import plt
#import collections
import pandas as pd

np.set_printoptions(suppress=True)

# aliases
ar=np.array

import segpy
from segpy import reader
from segpy import toolkit
from segpy import encoding

# TODO    
# Create a logger object.

#==============================================================================
# Commandline args
#==============================================================================
parser = argparse.ArgumentParser(
    formatter_class=argparse.RawDescriptionHelpFormatter,
    description=__doc__.split('\n\n\n')[0],
    epilog=__doc__.split('\n\n\n')[-1])
parser.add_argument('infile', type=str, help='Input ascii velovity file in western (velf) format.')
parser.add_argument('-o', '--outfile', type=str, default=None, help='Optional output segy filename, e.g. outfile.sgy. Defaults to infile.sgy. (default: %(default)s)') # default is same as input with different suffix
parser.add_argument('-s', '--sample-rate', type=int, default=None, help='If not provided this is autodetected from input data. The velocities are resampled to this rate in milliseconds. Must be <=32.767 (so it can be stored int16 is microseconds) (default: %(default)s)') # seem to need to be below 32.768ms
parser.add_argument('-m', '--max-time', type=float, default=None, help='If not provided this is autodetected from input data. The maximum time of the segy in ms. (default: %(default)s)') # max time
parser.add_argument('--dtype', default=1, type=int, help="Datatype for segy {8: 'int8', 1: 'ibm', 2: 'int32', 3: 'int16', 5: 'float32'}") # run tests?
parser.add_argument('-d', '--seismic-dimensions', type=int, default=3, help='Type of seismic, options 2 or 3.  (default: %(default)s)') 
parser.add_argument('-e', '--use-extended-header', action='store_true', default=False, help='Use the segy extended header in the output, this will contain the header from the text file. Defaults to false.  (default: %(default)s)') 
parser.add_argument('-v', '--verbosity', type=int, default=0, help="Print more information, can be 0, 1, or 2. (default: %(default)s)")
parser.add_argument('-t', '--test', default=False, action='store_true', help='Run sanity tests. (default: %(default)s)') # run tests?
args = parser.parse_args()


# check if the python running this is 64 bit
python_is_64=sys.maxsize > 2**32
if not python_is_64:
    print ("Warning you are not running in 64bit python, you will likely run into memory errors")
if sys.maxsize>os.path.getsize(args.infile)*41:
    print ("Warning you will likely run into memory errors")
    
#==============================================================================
# Set up params    
#==============================================================================
    
NUMPY_DTYPES = {'ibm':     np.dtype('f4'),
                'int32':   np.dtype('i4'),
                'int16':   np.dtype('i2'),
                'float32': np.dtype('f4'),
                'int8':    np.dtype('i1')}
SEG_Y_TYPE=segpy.datatypes.DATA_SAMPLE_FORMAT_TO_SEG_Y_TYPE[args.dtype]
DTYPE=NUMPY_DTYPES[SEG_Y_TYPE].type


    
#==============================================================================
# Read ascii data
#==============================================================================
    
def round_sf(x,n=2):
    '''Round to n sig figs'''
    return round(x, -int(np.round(np.log10(x)-n+1)))
    
class progress_bar(object):
    '''
    Simple progress bar that updates at a reporting interval. Useful for 
    reading in files.
    
    Usage:
        bar=progress_bar(max=os.path.getsize(f))
        for line in iter(fo.readline, ''): bar.update(fo.tell())
    '''
    def __init__(self,max,reports=100,msg=''):
        self.max=max
        self.n=np.log10(reports)
        self.intv=100/reports
        self.perc=0.0
        self.lastval=0.0
        self.val=0.0
        self.msg=msg
        
    def update(self,val):
        if val!=self.lastval: 
            self.lastval=self.val
            self.val=val
            self.last_perc=self.perc
            self.perc=100.0*round_sf(val/self.max,self.n+1)
            if self.perc!=self.last_perc and self.perc%self.intv==0:
                print(self.msg+"{:2.2f}%".format(self.perc))
    
def read_tsv_file(f):
    print ("Reading file", f )
    # read raw data
    fo=open(args.infile,'r')
    header=[]
    datar=[]
    bar=progress_bar(max=os.path.getsize(f),msg='    reading ',reports=10)
    for line in iter(fo.readline, ''):
        bar.update(fo.tell())
        sline=line.split()
            
        if line.startswith('#'):
            header.append(line)
        elif len(sline)>=5:
            fline=[DTYPE(s) for s in sline]
            x,y,t,v,inline,xline=fline[:6]
            datar.append([x,y,t,v,inline,xline])
        else:
            print ("Error could not parse line: '{}' ".format(line))
    fo.close()
    
    datar=np.array(datar)
    return datar,header


print ("Reading and sorting ascii file: {}".format(args.infile))
if not os.path.isfile(args.infile):
    print ("Error Input file not found!")
    exit(0)
datar,header=read_tsv_file(args.infile)
data=pd.DataFrame(datar,columns=['x','y','t','v','inline','xline']) 

    
#==============================================================================
# Process the data
#==============================================================================
#data.inline=data.inline.astype(int)
#data.xline=data.xline.astype(int)
    
# Sort data by inline then xline
data=data.sort_index(by=['inline','xline','t'])
trace_times=data.t
trace_vels=data.v


# make one unique index from inline and crossline, call it itrace
# so 10970 and 31000 becomes 10970*10^5+31000=1097031000
zeros_in_max_xline=int(np.ceil(np.log10(data.xline.max())))
data['itrace']=data.inline.multiply(10**zeros_in_max_xline)+data.xline
metadata=data.groupby(data.itrace).first() # one row for each trace


time_diffs=data.groupby(data.itrace).t.diff().dropna() # group by trace, for times get the difference, and drop NotANumbers
vel_diffs=data.groupby(data.itrace).v.diff().dropna()
traces=data.itrace.unique()
trace_lengths=data.itrace.groupby(data.itrace).count()


def angles(line):
    """get angles between points in line"""
    x=line[:,0]
    y=line[:,1]
    ang=np.arctan2(np.diff(x),np.diff(y))
    ang2=np.unwrap(ang)
    return np.array(ang2)

class grid(object):
    ''' init a seismic grid then use to convert between x,y and inline xline'''
    def __init__(self,p0,irot,ibin,xbin):
        '''
        p0, is a point in the array with attributes:
            p0.x, p0.y, p0.inline, p0.xline
        irot, is the inline rotation in radians
        ibin is the inline spacing 
        xbin is the xline spacing
        '''
        self.irot=irot
        self.ibin=ibin
        self.xbin=xbin
        self.inline=p0.inline
        self.xline=p0.xline
        self.x=p0.x
        self.y=p0.y
    
    def ix2xy(self,inline,xline):
        x=self.x+xbin*(xline-self.xline)*np.sin(self.irot)+ibin*(inline-self.inline)*np.cos(self.irot)
        y=self.y+xbin*(xline-self.xline)*np.cos(self.irot)-ibin*(inline-self.inline)*np.sin(self.irot)
        return  x,y
        
    def xy2ix(self,x,y):
        raise("Not implemented")
    

# lets work out the whole inline xline grid
inlines_r=pd.Series(data.inline.unique()) # inlines raw
xlines_r=pd.Series(data.xline.unique())
inline_int=inlines_r.diff().mode().values # choose interval as most common inline step, should I use min but ignore zero and nan?
xline_int=xlines_r.diff().mode().values
inlines=np.arange(inlines_r.min(),inlines_r.max(),inline_int)
xlines=np.arange(xlines_r.min(),xlines_r.max(),xline_int)

# find inline and xline with most data
xline_lens=metadata.xline.groupby(metadata.xline).count()
longest_xline_n=xline_lens.argmax()
longest_xline=metadata[metadata.xline==longest_xline_n]
inline_lens=metadata.inline.groupby(metadata.inline).count()
longest_inline_n=inline_lens.argmax()
longest_inline=metadata[metadata.inline==longest_inline_n]

if args.seismic_dimensions==3:
    # work out bins spacing
    ibins=pylab.distances_along_curve(longest_xline[['x','y']])/longest_xline.inline.diff().iloc[1:]
    ibin=ibins.mean()
    xbins=pylab.distances_along_curve(longest_inline[['x','y']])/longest_inline.xline.diff().iloc[1:]
    xbin=xbins.mean()
     
    inline_angs=angles(longest_inline[['x','y']].values)
    inline_rot=inline_angs.mean()
    xline_angs=angles(longest_xline[['x','y']].values)
    xline_rot=xline_angs.mean()

    pi=metadata.iloc[0] # reference point, might not be origin as we don't have that yet
    pj=metadata.iloc[100] # use this for a test
    gd=grid(pi,inline_rot,ibin,xbin)
    x,y=gd.ix2xy(pj.inline,pj.xline)
    
    # check the predicted coords are right withing a meter
    np.testing.assert_allclose(pj.x,x,atol=1) 
    np.testing.assert_allclose(pj.y,y,atol=1)


if args.test:
    # Some visual QC's
    plt.subplot(221)
    plt.title("Inline vs trace")
    plt.plot(data.inline)
    plt.subplot(222)
    plt.title("Xline vs trace")
    plt.plot(data.xline)
    plt.subplot(223)
    plt.title("Inlines vs xlines")
    plt.plot(data.inline,data.xline)
    plt.subplot(224)
    plt.title("x vs y")
    plt.plot(data.x,data.y)
    plt.show()
    
    # now show t vs v for 100 r traces
    plt.figure()
    plt.title("time vs velocity for 100 traces")
    plt.xlabel('v')
    plt.ylabel('t')
    trace_selection=np.arange(0,len(traces),100)
    for i in trace_selection:
        trace=data[data.itrace==traces[i]]
        plt.plot(trace.v,trace.t,label=str(traces[i]))
    plt.show()

#==============================================================================
# Sanity checks
#==============================================================================

print( "\nData summary")
print( data.describe())
print( data.info())
print( "\nTime intervals")
print( time_diffs.describe())
print("\nVel diffs")
print( vel_diffs.describe())
print("\nTrace lengths")
print(trace_lengths.describe())


# insert some sanity tests on the data here
# It should have increasing inlines?
# It should have more than one trace,  and more than one sample
assert(len(data)>1)
assert(len(trace_times)>1)


# sample times should be increasing  
np.testing.assert_( (time_diffs>=0).all()
    ,msg='Not all times increasing per trace: {}'.format(time_diffs[time_diffs<0]))

# I assertt it should be sorted
np.testing.assert_(np.alltrue(data.itrace.diff().dropna()>=0),msg="Data is not sorted")

# not NaN
assert(data.notnull().all().all())

# Inlines are not decimals
np.testing.assert_array_equal(data.inline,data.inline.astype(int),err_msg="Inlines are not integers")
# Crosslines are not decimals
np.testing.assert_array_equal(data.xline,data.xline.astype(int) ,err_msg="Crosslines are not integers")

print("\nInput data OK")

#==============================================================================
#  Get defaults args
#==============================================================================

if args.dtype not in segpy.datatypes.DATA_SAMPLE_FORMAT_TO_SEG_Y_TYPE:
    raise("--dtype must be one of ('ibm','int32','int16','float32','int8')")


if not args.outfile: 
    args.outfile=os.path.splitext(args.infile)[0]+'.segy'

if args.sample_rate==None:
    # work out if maxtime and samplesrate
    args.sample_rate=time_diffs[time_diffs!=0].mode()[0]
    if  args.sample_rate>=32.767:
        print("Sample rate can't be bigger than 32767, changed from {} to 32767".format(args.sample_rate))
        args.sample_rate=32.767

    print ("No sample rate provided, using mode of: {}".format(args.sample_rate))

if args.max_time==None:
    args.max_time=data.t.max()
    print ("Auto detected maxtime of {:f}".format(args.max_time))
    
tmin = data.t.min()
print ("Auto detected mintime of {:f}".format(tmin))


#==============================================================================
# Format file header into segy header
#==============================================================================
#format_header='.'.join(header).replace('  ',' ').replace('\n','\\')

def minify(s):
    if isinstance(s,list):
        s='\n'.join([h.strip() for h in s])
    import re
    s=re.sub(' +',' ',s)
    return s    

if not isinstance(header,list): # in case its merely one string
    header=[header]
if any(ar([len(s) for s in header])>80): # if they are all shorted than 80
    header=minify(header) # else wrapthem and remove extra whitespac
    split_header=[]
    inds=range(0,len(header),80)
    for i in range(len(inds)-1):
        header_line=header[inds[i]:inds[i+1]]
        split_header.append(header_line)
else:
    split_header=header
info_header=[
    "CREATED from ascii using ascii2segy.py, (uses: github.com/rob-smallshire/segpy)",
    "INPUT: {}".format(os.path.split(args.infile)[1]),
    "DATE: {}, USER: {}@{}".format(datetime.datetime.now().isoformat(),os.getenv('USERNAME'),os.getenv('USERDNSDOMAIN')),
    '############## Header information from input file ##############',
    ]
joined_header=info_header+split_header
textual_reel_header=joined_header+(40-len(joined_header))*[' '*80]
# remove extra
textual_reel_header=[s[:80]+(80-len(s))*' ' for s in textual_reel_header]
textual_reel_header=textual_reel_header[:40]


#==============================================================================
# Write SEGY
#==============================================================================
#TODO make these options
segyencoding=encoding.EBCDIC
endian='>'

# times to interpolate onto
itimes=np.arange(tmin,args.max_time+args.sample_rate,args.sample_rate) 
    
template_trace=segpy.trace_header.TraceHeaderRev1()
template_binary_reel_header=segpy.binary_reel_header.BinaryReelHeader()   
                         
print ("Writing segy {}".format(args.outfile))
with open(args.outfile,'wb') as fo:
    
    # Format text header
    if args.use_extended_header: 
        print ("Formating extended textual header")
        extended_textual_header=toolkit.format_extended_textual_header('',segyencoding)
    else:
        extended_textual_header=toolkit.format_extended_textual_header(''.join(header),segyencoding)
    
    #Format binary header
    binary_reel_header=template_binary_reel_header
    binary_reel_header.sample_interval=int(args.sample_rate*1000) # samples length microseconds    
    binary_reel_header.num_samples=len(itimes) # number of samples
    binary_reel_header.data_traces_per_ensemble=0 # len(data) # also must be # not sure how to work this out, maybe I need to scan the file first or after insert it
    binary_reel_header.auxiliary_traces_per_ensemble=0
    binary_reel_header.trace_sorting=4 # http://oivdoc91.vsg3d.com/APIS/RefManCpp/struct_so_v_r_segy_file_header.html#a612dab3b4d9c671ba6554a8fb4a88057
    binary_reel_header.format_revision_num=256 # 0 or 1 TODO move to 1
    binary_reel_header.data_sample_format=args.dtype # see binary header def.py file as it changes by revision. 1 is always ibm float
    if args.use_extended_header: binary_reel_header.num_extended_textual_headers=len(extended_textual_header) # see binary header def.py file as it changes by revision. 1 is always ibm float
    
    # Write headers
    toolkit.write_textual_reel_header(fo, textual_reel_header, segyencoding)
    toolkit.write_binary_reel_header(fo, binary_reel_header, endian)
    if args.use_extended_header: toolkit.write_extended_textual_headers(fo, extended_textual_header, segyencoding)
    
    # Pre-Format trace headerf
    trace_header_format = toolkit.make_header_packer(segpy.trace_header.TraceHeaderRev1,endian)
        
    if args.seismic_dimensions==3:
        # either iterate over the grid for 3d
        xxlines,iinlines=np.meshgrid(xlines,inlines)
        trace_iter=np.vstack([iinlines.flat,xxlines.flat]).T
    else:
        # or for 2d just iterate over cdp an sp
        trace_iter=np.vstack([inlines_r,xlines_r]).T
    
    i=0
    tracen=1
    for inline,xline in trace_iter:
        i+=1
        if ((metadata.inline==inline)*(metadata.xline==xline)).any():
            trace=data[(data.inline==inline) * (data.xline==xline)]   
            metatrace=metadata[(metadata.inline==inline) * (metadata.xline==xline)]  
            x=metatrace.x
            y=metatrace.y
            times=trace.t.values
            vels=trace.v.values
        elif args.seismic_dimensions==3:
            x,y=gd.ix2xy(inline,xline)
            times=itimes
            vels=np.zeros(itimes.shape)
        else:
            print("inline/xline or cdp/sp not found",inline,xline)
        
        cdp=inline
        sp=xline
            
        
        if i%1000==0:
            print ("Writing trace: {: 8.0f}/{}, {: 6.2f}%".format(i,len(trace_iter),(1.0*i/len(trace_iter))*100))
        
        if len(vels)==0:
            print ("Error no vels on trace", i)
            continue     
        
        # interpolate data
        samples=np.interp(itimes,times,vels)
        
        # ensure datatype is ok
        samples =np.require(samples, dtype='d')
        
        # Format trace header
        trace_header=template_trace
        trace_header.line_sequence_num=1000+tracen
        trace_header.field_record_num=tracen
        trace_header.trace_num=tracen
        if args.seismic_dimensions==3:
            trace_header.file_sequence_num=inline
            trace_header.ensemble_num=xline
            trace_header.inline_number=inline
            trace_header.crossline_number=xline
        else:
            trace_header.file_sequence_num=1000+tracen
            trace_header.ensemble_num=cdp
            trace_header.shotpoint_number=sp
        trace_header.num_samples=len(samples) # number of samples
        trace_header.sample_interval=args.sample_rate # sample interval
        trace_header.cdp_x=x
        trace_header.cdp_y=y
        trace_header.source_x=x
        trace_header.source_y=y
        
        # write trace header and data 
        toolkit.write_trace_header(fo, trace_header, trace_header_format, pos=None)
        toolkit.write_trace_samples(fo, samples=samples, seg_y_type=SEG_Y_TYPE, endian=endian, pos=None)
        
        tracen+=1
    print ("Writing trace: {: 8.0f}/{}, {: 6.2f}%".format(i,len(trace_iter),(1.0*i/len(trace_iter))*100))
    print( "Done")
    if not fo.closed: fo.close()

if args.test:
    #Validate outfile
    from segpy.reader import create_reader
    from segpy.writer import write_segy
    def load_save(in_filename, out_filename):
        with open(in_filename, 'rb') as in_file, \
             open(out_filename, 'wb') as out_file:
    
            segy_reader = create_reader(in_file)
            print()
            print("Filename:             ", segy_reader.filename)
            print("SEG Y revision:       ", segy_reader.revision)
            print("Number of traces:     ", segy_reader.num_traces())
            print("Data format:          ",
                  segy_reader.data_sample_format_description)
            print("Dimensionality:       ", segy_reader.dimensionality)
    
            try:
                print("Number of CDPs:       ", segy_reader.num_cdps())
            except AttributeError:
                pass
    
            try:
                print("Number of inlines:    ", segy_reader.num_inlines())
                print("Number of crosslines: ", segy_reader.num_xlines())
            except AttributeError:
                pass
    
            print("=== BEGIN TEXTUAL REEL HEADER ===")
            for line in segy_reader.textual_reel_header:
                print(line[3:])
            print("=== END TEXTUAL REEL HEADER ===")
            print()
            print("=== BEGIN EXTENDED TEXTUAL HEADER ===")
            print(segy_reader.extended_textual_header)
            print("=== END EXTENDED TEXTUAL_HEADER ===")
            write_segy(out_file, segy_reader)
    
    print( "Validating segy file")
    outfile2=args.outfile.replace('.segy','-test.segy').replace('.sgy','-test.sgy')
    try:
        load_save(args.outfile, outfile2)
    except Exception as e:
        print( "Error: Error code while validating output:", e)
    else:
        print( "segy file OK")
    os.remove(outfile2)

    