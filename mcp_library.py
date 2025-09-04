# -*- coding: utf-8 -*-
"""
Created on Thu Aug 21 14:00:45 2025

This is a set of MCP commands for the TEAM 0.5 microscope and the 
4D Camera.

@author: alexa
"""

import io
import base64

import pickle
import time
import numpy as np
import numpy.typing as npt
import zmq

from fastmcp import FastMCP, Image
from datetime import datetime, timedelta
from typing import Any, Optional

import requests
from pydantic import AnyHttpUrl, BaseModel, ConfigDict
from pydantic_settings import BaseSettings, SettingsConfigDict
from requests.exceptions import HTTPError, RequestException
import argparse

mcp = FastMCP("TEAM05_Controller")

# from PIL import Image

import sys
sys.path.insert(0, 'D:/user_data/Pattison/BEACON')
from GUI_Client import BEACON_Client

@mcp.tool()
def team05_greet_me(username):
    """Function to say hello to a user who wants to control the team05"""
    return f'Hello {username}. Welcome to the TEAM0.5'



# Microscope (BEACON) server commands
@mcp.tool()
def acquire_ceos_tableau():
    d = {'type': 'tableau'}
    Response = microscope_client.send_traffic(d)
    tableau_results = Response['reply_data']
    return tableau_results

@mcp.tool()
def change_aberrations(ab_values:dict):
    '''
    Change aberrations without acquiring image.
    Aberrations are NOT reset to current values after function call.
    Some common names of the aberrations are:
    C1 is defocus and is one-dimensional.
    A1 is 2-fold astigmatism and has an x and y component
    B2 is coma and has an x and y component
    C3 is the thrid-order shperical aberration (sometimes just called the spherical aberration) and is one-dimensional.

    Parameters
    ----------
    ab_values : dict
        Dictionary of values by which to change aberrations. Values are in metres. 
        Keys are 'C1', 'A1_x', 'A1_y', 'B2_x', 'B2_y', 'A2_x', 'A2_y', 'C3', 'S3_x', 'S3_y', 'A3_x', 'A3_y'.
        The values for each aberration are a float.

    Returns
    -------
    None.

    '''
    ab_select = {'C1': None,
                 'A1_x': 'coarse',
                 'A1_y': 'coarse',
                 'B2_x': 'coarse',
                 'B2_y': 'coarse',
                 'A2_x': 'coarse',
                 'A2_y': 'coarse',
                 'C3': None,
                 'A3_x': 'coarse',
                 'A3_y': 'coarse',
                 'S3_x': 'coarse',
                 'S3_y': 'coarse',
                 }

    C1_defocus_flag = True
    undo = False
    bscomp = False
    
    d = {'type': 'ab_only',
         'ab_values': ab_values,
         'ab_select': ab_select,
         'C1_defocus_flag': C1_defocus_flag,
         'undo': undo,
         'bscomp': bscomp,
         }
    Response = microscope_client.send_traffic(d)
    print(Response)

@mcp.tool()
def set_reference_image(dwell:float=2e-6, shape:tuple=(256,256)):
    '''
    Acquire a new STEM image with the function input settings. The 
    BEACON server then users this image as the reference image
    for cross-correlation analysis of all future images.

    Parameters
    ----------
    dwell : float, optional
        Dwell time in seconds. The default is 2e-6 seconds.
    shape : tuple of ints, optional
        Image shape in pixels. The default is (256,256) pixels.

    Returns
    -------
    None.
    
    '''

    d = {'type': 'ref', 'dwell': dwell, 'shape': shape}
    microscope_client.send_traffic(d)


@mcp.tool()
def move_stage_delta(dX:float=0, dY:float=0, dZ:float=0, dA:float=0, dB:float=0):
    '''
    Moves and tilts stage relative to the current position. The values
    of dX, dY, and dZ are in are in meters. The maximum value that should be allowed is 10 microns
    or 10e-5 meters. The values of dA and dB are angles which are used to tilt the stage to bring
    a crystal on axis. dA is similar to roll and dB is similar to pitch in an airplane. There is 
    no way to implement a yaw rotation in a TEM.

    Parameters
    ----------
    dX : float, optional
        Change in x position in mteres. The default is 0.
    dY : float, optional
        Change in y position in meters. The default is 0.
    dZ : float, optional
        Change in z position in meters. The default is 0.
    dA : float, optional
        Change in alpha angle in radians. The default is 0.
    dB : float, optional
        Change in beta alngle in radians (may require adjustment to server to work). The default is 0.

    Returns
    -------
    None.

    '''
    dPos = {'type':'move_stage', 'dX':dX, 'dY':dY, 'dZ':dZ, 'dA':dA, 'dB':dB}
    microscope_client.send_traffic(dPos)

@mcp.tool()
def acquire_image(dwell:float=2e-6, shape:tuple =(256,256)):
    '''
    Acquire HAADF-STEM image. A tuple is returned with the 
    image and calibration information.
    
    Parameters
    ----------
    dwell : float
        Dwell time in seconds
    shape : tuple
        Image shape as a tuple. The first element is the width and the second element is the height
    
    Returns
    -------
    : tuple (list, float, float, string, float, float, float)
        The tuple is made of 4 elements. The description of the elements are 
        (image as a list, x pixel calibration, y pixel calibration, the calibration unit name,
        the image minimum, the image maximum, and the image standard deviation).
    '''
    print(type(dwell), type(shape))
    
    offset = (0, 0) # hard coded for now
    d = {'type': 'image', 'dwell': dwell, 'shape': shape, 'offset': offset}
    Response = microscope_client.send_traffic(d)
    if Response is None:
        return None
    
    (image, calx, caly, cal_unit_name) = Response['reply_data']
    image_min = image.min()
    image_max = image.max()
    image_std = image.std()
    
    simple_image = image.tolist()
    
    return (simple_image, calx, caly, cal_unit_name, image_min, image_max, image_std)

@mcp.tool()
def get_mag():
    '''
    Get current STEM magnification as an integer.

    Returns
    -------
    : int
        Current magnification.

    '''
    d = {'type': 'get_mag'}
    Response = microscope_client.send_traffic(d)
    mag = Response['reply_data']
    return mag

@mcp.tool()
def get_stage_pos():
    '''
    Get the stage parameters. The stage x, y and z parameters are 
    in meters. The stage alpha and beta tilt parameteres are in radians.

    Returns
    -------
    : tuple (float, float, float, float, float)
        The current stage parameters. The returned tuple 
        has 5 elements in the order
        (x position, y position, z position, alpha angle, beta angle)

    '''
    d = {'type': 'get_stage_pos'}
    Response = microscope_client.send_traffic(d)
    stage_position = Response['reply_data']
    return stage_position

@mcp.tool()
def get_camera_length():
    '''
    Get current STEM camera length. The camera length is in meters.

    Returns
    -------
    : float
        STEM camera length in meters.

    '''
    d = {'type': 'get_camera_length'}
    Response = microscope_client.send_traffic(d)
    CL = Response['reply_data']
    return CL
   
@mcp.tool()
def get_camera_length_index():
    '''
    Get current STEM camera length index. It can be used to determine
    the actual camera length by indexing into the list of camera lenght
    names.
    
    Returns
    -------
    None.

    '''
    d = {'type': 'get_camera_length_index'}
    Response = microscope_client.send_traffic(d)
    CL_index = Response['reply_data']
    return CL_index

@mcp.tool()
def set_mag(mag:int):
    '''
    Set the STEM magnification.
    
    Parameters
    ----------
    mag : int
        Magnification value.

    Returns
    -------
    None.

    '''
    d = {'type': 'set_mag', 'mag': mag}
    microscope_client.send_traffic(d)

@mcp.tool()
def set_camera_length_index(CL_index:int):
    '''
    Set the STEM camera length index value.
    The names of several common index values are as follows:
    CL_index == 5 is 85 mm
    CL_index == 6 is 105 mm

    Parameters
    ----------
    CL_index : int
        Camera length index.

    Returns
    -------
    None.

    '''
    d = {'type': 'set_camera_length_index', 'CL_index': CL_index}
    microscope_client.send_traffic(d)

@mcp.tool()
def open_column_valve():
    '''
    Opens the column valves. 

    Returns
    -------
    str: reply message

    '''
    d = {'type': 'open_column_valve'}
    Response = microscope_client.send_traffic(d)
    print(Response)
    return(Response)
   
@mcp.tool()
def close_column_valve():
    '''
    Close the column valves.

    Returns
    -------
    str: reply message.

    '''
    d = {'type': 'close_column_valve'}
    Response = microscope_client.send_traffic(d)
    print(Response)
    return(Response)

# called by registration
def cross_correlate(im0:npt.NDArray, im1:npt.NDArray):
    '''
    Cross-correlate two images input as 2D numpy arrays. 

    Parameters
    ----------
    im0 : numpy.ndarray
        The reference image. 
    im1 : numpy.ndarray
        The image to cross-correlate.

    Returns
    -------
    : numpy.ndarray
     The numpy array returned is the cross-correlation of the two images.

    '''
    p0 = np.zeros((im0.shape[0], im0.shape[1]))
    p1 = np.zeros((im0.shape[0], im0.shape[1]))
    p1[p1.shape[0]//2-im1.shape[0]//2:p1.shape[0]//2-im1.shape[0]//2 + im1.shape[0],
       p1.shape[1]//2-im1.shape[1]//2:p1.shape[1]//2-im1.shape[1]//2 + im1.shape[1]] = im1
    f0 = np.fft.fft2(im0)
    f1 = np.fft.fft2(p1)
    f0 *= np.conj(f1)
    c = np.fft.ifft2(f0)
    return np.fft.fftshift(c.real)

# called by centering 
def registration(refImage:npt.NDArray, curImage:npt.NDArray, pixelSize:float):
    '''
    Find the offset between two images using cross correlation. The ouptut is in
    terms of the pixelSize which is usually in meters..

    Parameters
    ----------
    refImage : numpy.ndarray
        Reference image.
    curImage : numpy.ndarray
        Current image.
    pixelSize : float
        Real-space pixel calibration. This is usually in meters.

    Returns
    -------
    offset_xy : tuple (offset x, offset y)
        offset between two images. This is in terms of the pixelSize input.

    '''
    corr = cross_correlate(curImage-curImage.mean(), refImage-refImage.mean())
    corr_arg = np.array(np.unravel_index(np.argmax(corr), corr.shape))
    offset = (corr_arg-np.array(refImage.shape)/2)
    offset_xy = offset*pixelSize
    #print(offset_xy)
    return offset_xy

# called by centering
def _focusing(df_range:float=1000e-9):
    range_dict = {'C1': [-df_range,df_range]}

    init_size_value = 5
    runs_value = 10
    func_value = 'ucb'

    dwell_value = 3e-6
    shape_value = (512,512)
    offset_value = (0, 0)
    metric_value = 'normvar'

    return_images = True
    bscomp = False
    ccorr = True

    beacon_client.ae_main(range_dict,
                          init_size_value, 
                          runs_value,
                          func_value,
                          dwell_value, 
                          shape_value,
                          offset_value,
                          metric_value,
                          return_images,
                          bscomp,
                          ccorr,
                          C1_defocus_flag=True,
                          ab_select=None,
                          #custom_ucb_factor=3,
                          noise_level=1e-4)

    mm = beacon_client.model_max
    ab_keys = beacon_client.ab_keys
    ab_values = {}
    for i in range(len(ab_keys)):
        ab_values[ab_keys[i]] = mm[i]*1e-9

    beacon_client.ab_only(ab_values)

@mcp.tool()
def focusing(df_range:float=1000e-9):
    '''
    Performs autofocusing using BEACON. This is a Bayesian optimization 
    routine which searches with the specified range for the best
    focus. The best focus is set on the microscope automatically.

    Parameters
    ----------
    df_range : float in meters
        Maximum values plus and minus from the current defocus to 
        search. The default is 1000e-9 meters.

    Returns
    -------
    None.

    '''
    
    _focusing(df_range)
    

def centering(refImage:npt.NDArray, xymax:float=100e-9, ntries:int=4, df_range:float=None, 
              cal_factor:float=1.0, dwell_search:float=2e-6, size_search:int=256):
    '''
    Center the image on the position shown in the reference image. This uses crosscorrelation 
    to move the stage such that microscope is centered on the objects in the reference image.
    
    Parameters
    ----------
    refImage : numpy.ndarray
        Image of target area.
    xymax : float, optional
        Maximum acceptable offset between actual and target position. The default is 100e-9 meters.
    ntries : int, optional
        Number of attempts to center the image. The default is 4 tries.
    df_range : float, optional
        Defocus range for autofocusing in meters. The default is None. If None then no autofocusing is performed.
    cal_factor : float, optional
        Calibrate stage movement to image resolution. The default is 1.0.
    dwell_search : float, optional
        Dwell time in seconds. The default is 2e-6.
    size_search : int, optional
        Image size in pixels. The image will be square. The default is 256.

    Raises
    ------
    ValueError
        Fails if number of attempts to center exceeds ntries.

    Returns
    -------
    None.

    '''
    NOT_CENTERED = True
    
    while NOT_CENTERED and ntries > 0:
        if df_range is not None:
            _focusing(df_range)
        
        curImage, pixelSize = acquire_image(dwell_search, size_search)
        
        offset = registration(refImage, curImage, pixelSize) # Perform registration
        print('offset = ', offset) # for debugging
        if abs(offset[0]) > xymax or abs(offset[1]) > xymax: # Move if needed
            ntries +=-1
            move_stage_delta(dX=offset[0]*cal_factor, dY=offset[1]*cal_factor) # y may need -ve sign depending on which side of the horizontal axis it's on!!! Need to look into this!
            time.sleep(1)
        else:
            NOT_CENTERED = False
            print('Centered')
    
    if NOT_CENTERED and ntries <= 0:
        d = {'type': 'close_column_valve'}
        microscope_client.send_traffic(d)
        print('Closing column valve')
        raise ValueError('Number of attempts to center has exceeded ntries')

@mcp.tool()
def get_screenshot():
    '''
    Take a screenshot of the microscope GUI.
    
    Returns
    -------
    : PIL.Image
        The image a a PIL Image object.
    '''
    d = {'type': 'get_screenshot'}
    Response = microscope_client.send_traffic(d)
    image = Response['reply_data']
    im = io.BytesIO()
    image.save(im, format='PNG')
    im.seek(0)
    encoded_image = base64.b64encode(im.getvalue()).decode('utf-8')
    
    return Image(encoded_image)

@mcp.tool()
def blank_beam():
    '''
    Blank the beam
    
    Returns
    -------
    str: reply message.
    
    '''
    d = {'type': 'blank_beam'}
    Response = microscope_client.send_traffic(d)
    return Response['reply_message']

@mcp.tool()
def unblank_beam():
    '''
    Unblank the beam
    
    Returns
    -------
    str: reply message.
    
    '''
    d = {'type': 'unblank_beam'}
    Response = microscope_client.send_traffic(d)
    return Response['reply_message']

@mcp.tool()
def get_voltage():
    '''
    Find the accelerating voltage of the microscope
    
    Returns
    -------
    voltage: float.
        Accelerating voltage of the microscope in volts
    
    '''
    d = {'type': 'get_voltage'}
    Response = microscope_client.send_traffic(d)
    voltage = Response['reply_message'] 
    return voltage

@mcp.tool()
def get_defocus():
    '''
    Find the defocus of the microscope
    
    Returns
    -------
    defocus: float.
        Current defocus value of the microscope in metres
    
    '''
    d = {'type': 'get_defocus'}
    Response = microscope_client.send_traffic(d)
    df = Response['reply_message'] 
    return df

@mcp.tool()
def set_defocus(target_df:float=0e-9):
    '''
    Set the defocus of the microscope
    
    Returns
    -------
    defocus: float.
        Current defocus value of the microscope in metres
    
    '''
    d = {'type': 'set_defocus', 'target_df': target_df}
    Response = microscope_client.send_traffic(d)
    df = Response['reply_message'] 
    return df

# Gatan server commands
@mcp.tool()
def move_beam_dm(dX:int, dY:int):
    '''
    Move the beam parking position in Digital Micrograph.

    Parameters
    ----------
    dX : int
        Move beam in X (pixels).
    dY : int
        Move beam in Y (pixels).

    Returns
    -------
    None.

    '''
    gatan_client.send_traffic(('move_beam', (dY, dX)))
    
@mcp.tool()
def acquire_4D_scan(width:int, height:int):
    '''
    Acquire a 4D-STEM scan.  This takes a data set using the 4D Camera.
    
    Parameters
    ----------
    height : int
     The height in pixels of the 4D-STEM scan
    width : int
     The width in pixels of the 4D-STEM scan

    Returns
    -------
    None.
    
    '''
    params = {'ptime':11e-6, 'pwidth':width, 'pheight':height, 'emd':None}
    gatan_client.send_traffic(('set_gatan', 0)) # set gatan for 4D scan
    gatan_client.send_traffic(('take_and_return_data', params))
    gatan_client.send_traffic(('set_tia', 0)) # set tia for x-corr


class Microscope_Client():
    def __init__(self, host='192.168.0.24', port=7001):
        try:
            # Set timeout in milliseconds
            timeout_ms = 10000  # 1 second
            context = zmq.Context()
            self.ClientSocket = context.socket(zmq.REQ)
            
            self.ClientSocket.setsockopt(zmq.RCVTIMEO, timeout_ms)
            self.ClientSocket.setsockopt(zmq.SNDTIMEO, timeout_ms)
            self.ClientSocket.connect(f"tcp://{host}:{port}")
            #print(f'Connected to BEACON server at {host}:{port}')
            
        except ConnectionRefusedError:
            print('Start the BEACON server')
            exit()
    
    def send_traffic(self, message):
        '''
        Sends and receives messages from the server.
        
        Parameters
        ----------
        message : dict
            Message for the server.
        
        Returns
        -------
        response : dict
        
            Response from the server.
        '''
        print(f'Microscope_Client: {message}')
        try:
            self.ClientSocket.send(pickle.dumps(message))
            response = pickle.loads(self.ClientSocket.recv())
            return response
            
        except zmq.Again:
            print("Timeout occurred")
            return None
        


class Gatan_Client():
    def __init__(self, host='192.168.0.30', port=13579):
        try:
            context = zmq.Context()
            self.ClientSocket = context.socket(zmq.REQ)
            self.ClientSocket.connect(f"tcp://{host}:{port}")
            print('Connected')
        except ConnectionRefusedError:
            print('Start the multiscan server')
            exit()
        
    def send_traffic(self, message):
        '''
        Sends and receives messages from the server.
        
        Parameters
        ----------
        message : dict
            Message for the server.
        
        Returns
        -------
        response : dict
            Response from the server.
        '''
        print(f'Gatan_Client: {message}')
        self.ClientSocket.send(pickle.dumps(message))
        response = pickle.loads(self.ClientSocket.recv())
        return response


if __name__ == "__main__":
    mhost = '192.168.0.24'
    mport = 7001
    
    microscope_client = Microscope_Client(mhost, mport) # Communicate with microscope PC
    
    beacon_client = BEACON_Client(mhost, mport) # Communicate with microscope PC
    
    d = {'type': 'ping'}
    Response = microscope_client.send_traffic(d)
    print(Response['reply_message'])

    
    ghost = '192.168.0.30'
    gport = 13579

    gatan_client = Gatan_Client(ghost, gport)
    
    print(get_voltage())
    print(get_defocus())
    print(set_defocus())
    
    #mcp.run(transport = "sse", host = "team05-support.dhcp.lbl.gov", port = 8080)