# -*- coding: utf-8 -*-
"""
This is a python script to convert from  this format:
'
LINE      PEG0906M1000         
SPNT                 8188
VELF    0 1480 2408 1485 2667 1506 2950 1557 3072 1581
VELF 3402 1633 3613 1686 3705 1716 3873 1768 4033 1820
'
to coloumns seperated by tabs


version 0.0.1


author:michael clark
2015
"""
import sys, os, re, datetime
import math

#==============================================================================
# Commandline args
#==============================================================================
import argparse
parser = argparse.ArgumentParser(
    formatter_class=argparse.RawDescriptionHelpFormatter,
    description=__doc__.split('\n\n\n')[0],
    epilog=__doc__.split('\n\n\n')[-1])
parser.add_argument('infiles', type=str, help='Input ascii velovity file in western (velf) format.', nargs='*')
#parser.add_argument('-o', '--outfile', type=str, default=None, help='Optional output segy filename, e.g. outfile.tsv. Defaults to infile.tsv. (default: %(default)s)') # default is same as input with different suffix
parser.add_argument('-c', '--constant-velf-space', type=int, default=20, help='How many coloumns before velf data begins. (default: %(default)s)') 
parser.add_argument('-n', '--column-width', type=int, default=5, help='Columns width for each velocity and time datapoint. (default: %(default)s)') 
#parser.add_argument('-f', '--fixed-width', default=True, help='Read the columns as fixed width. (default: %(default)s)') 
parser.add_argument('-v', '--verbose', type=int, default=0, help="Print more information, can be 0, 1, or 2. (default: %(default)s)")
parser.add_argument('-s', '--stopat', type=int, default=None, help="Stop after X many lines, for testing")
#parser.add_argument('-t', '--test', default=False, help='Run sanity tests. (default: %(default)s)') # run tests?
args = parser.parse_args()


infiles=args.infiles
c=args.constant_velf_space
n=args.column_width
verbose=args.verbose

# TODO velf to essov2 instead of tsv

headstr="""# x (m in NZGD2000)\ty (m in NZGD2000)\ttime (from VELF files)\tvel (from VELF file)\tline
# Converted on {} from {} by {}@{} using process_stacking_velocity_files_to_tsv.py.
# Start header from original file :
###############################################################################
"""
headstr2="" # fulled in as we go
headstr3="""
###############################################################################
#End header from original file
VERSION 1
BEGIN HEADER
X
Y
Z
FLOAT  "Stacking Velocity"
FLOAT  "XLINE"
FLOAT  "INLINE"
END HEADER
"""

outf=outf2=infile=None
for f in infiles:
    if infile: infile.close()  
    if os.path.isfile(f):
        infile=open(f,'r')
   
        # init
        vels=[]
        times=[]
        cdps=dict()
        line_name=''
        x=y=inline=xline=sp=cdp=0
        inHeader=True
        # open/close files
        if outf: outf.close()
        if outf2: outf2.close()
        outf=open(f+'.tsv','w') # tab seperated values ascii
        outf.write(headstr.format(
            datetime.datetime.now().isoformat(),
            os.path.split(f)[1],
            os.getenv('USERNAME'),
            os.getenv('USERDNSDOMAIN'))
            )
        outf.write(headstr2)

        #outf2=open(f+'.essov2','w') # esso v2 stackign velocity format files
        
        linenum=0
        print "Reading ", infile
        for line in infile:
            linenum+=1
            if args.stopat and linenum>=args.stopat:
                print "Stopped at line", args.stopat, "due to argument --stopat"
                break
            
            if line.startswith("VELF") and len(line)>6:
                # write to coloumn
                s=line[c:].rstrip('\n')
                data=[s[i:i+n] for i in range(0, len(s), n)]
                for i in range(len(data)):
                    if i%2==0:
                        times.append(float(data[i]))
                    else:
                        vels.append(float(data[i]))
                
                cdp=int(math.floor(float(cdp))) # make it a integer even if it has .0 (e.g. one point zero -> one)
    
            elif line.startswith("SPNT") and len(line)>6:
                if inHeader:
                    outf.write(headstr3)
                    inHeader=False
                # start a new coloumn
                for i in range(len(vels)):
                    v=vels[i]
                    t=times[i]
                    outstr=("{: >10}\t"*6+"\n").format(x,y,t,v,inline,xline)           
                    outf.write(outstr)
                    #outstr="{: <8}{: >7}{: >20}{: >25}\n".format("V2"+line_name.upper(),sp,t,v) 
                    #outf2.write(outstr)
                
                vels=[]
                times=[]
                s = line[4:].strip('\n')
                s = s.split()
                xline=float(s[1])                
                x=float(s[2])
                y=float(s[3])
                inline=float(s[4])
                sp=float(s[5]) 
                cdp=0
                
                    
                # print out some
            elif line.startswith("LINE") and len(line)>6:
                line=int(line[4:].strip())
            else:
                if inHeader:
                    outf.write('#'+line)
                else:
                    print "Can't parse (comment?) line", line
                    
        print "Writing file", outf
        for i in range(len(vels)):
            v=vels[i]
            t=times[i]
            outstr=("{: >10}\t"*6+"\n").format(x,y,t,v,inline,xline)          
            outf.write(outstr)
            #outstr="{: <8}{: >7}{: >20}{: >25}\n".format("V2"+line_name.upper(),sp,t,v) 
            #outf2.write(outstr)        
        infile.close()

outf.close()
#outf2.close()