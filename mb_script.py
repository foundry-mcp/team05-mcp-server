# -*- coding: utf-8 -*-
"""
Created on Sun Apr  3 19:55:21 2022

@author: ajpattison
"""

def move_beam_dm(dX, dY):
    return f""" // move beam
    
image im := GetFrontImage()
String imName = im.ImageGetName()

number X, Y, currX, currY

DSGetBeamDSPosition(currX, currY)
DSCalcImageCoordFromDS(im, currX, currY, X, Y)
number newX = X+{dX}
number newY = Y+{dY}
DSPositionBeam(im, newX, newY)
Result("Beam moved by {dX}, {dY}\\n")
"""