# -*- coding: utf-8 -*-
"""
Created on Thu Aug 21 14:00:45 2025

This is a set of MCP commands for the TEAM 0.5 microscope and the 
4D Camera. It sends commands to the microscope_server(s) running on
the microscope PC and on the Gatan PC.

@author: Peter Ercius, Alex Pattison, Morgan Wall, Stephanie Ribet
"""

from pathlib import Path
import io
import base64
import argparse
import time
from datetime import datetime, timedelta
from typing import Any, Optional

import pickle
import numpy as np
import numpy.typing as npt
import zmq

from fastmcp import FastMCP
from fastmcp.utilities.types import Image as mcpImage

from fastmcp.resources import FileResource
from pathlib import Path
from fastmcp.utilities.types import Image as mcpImage
from datetime import datetime, timedelta
from typing import Any, Optional

import requests
from pydantic import AnyHttpUrl, BaseModel, ConfigDict
from pydantic_settings import BaseSettings, SettingsConfigDict
from requests.exceptions import HTTPError, RequestException

import h5py
import mfid

mcp = FastMCP("TEAM05_Controller")

from PIL import Image as pilImage

import sys
sys.path.insert(0, 'D:/user_data/Pattison/BEACON')
from GUI_Client import BEACON_Client

@mcp.resource("file://TEAM0.5_parameters.txt", mime_type="text/plain")
def get_team05_parameter_configurations():
    with open('TEAM0.5_parameters.txt', mode="r") as f:
        info = f.read()
        return info


def get_metadata():
    """ Get metadata from the microscope. 
    
    Returns
    -------
    : dict
    A dictionary with lots of different STEM metadata.
    
    """
    d = {'type': 'get_metadata'}
    Response = microscope_client.send_traffic(d)
    if Response['reply_data'] is None:
        raise Exception('Command failed.')
    else:
        reply_data = Response['reply_data']
        return reply_data

def create_dims(dataTop, pix):
    """ Create dims for the EMD file."""

    dim2 = dataTop.create_dataset('dim2',(pix,),'f')
    dim2.attrs['name'] = 'X'
    dim2.attrs['units'] = 'n_m'
    dim1 = dataTop.create_dataset('dim1',(pix,),'f')
    dim1.attrs['name'] = 'Y'
    dim1.attrs['units'] = 'n_m'

    return 1

def write_emd_data(file_path, data, calX, calY, user_name='Claude', sample_name=''):
    with h5py.File(file_path, 'w') as f:
        sh = data.shape
        microscope_name = 'TEAM 0.5'
        md = get_metadata()
        
        dataroot = f.create_group('/data')
        
        # Initialize the data set
        dataTop = dataroot.create_group('single')
        dset = dataTop.create_dataset('data', sh, data.dtype)
        
        # Create the EMD dimension datasets
        _ = create_dims(dataTop, 'single', sh[0])
        
        microscope = f.create_group('microscope')
        microscope.attrs['microscope name'] = 'TEAM 0.5'
        microscope.attrs['high tension'] = md['high tension']
        microscope.attrs['spot size index'] = md['spot size index']
        microscope.attrs['magnification'] = md['magnification']
        microscope.attrs['defocus'] = md['defocus']
        microscope.attrs['convergence angle'] = md['convergence angle']
        microscope.attrs['camera length'] = md['camera length']
        microscope.attrs['stage position'] = md['stage position']

        user = f.create_group('user')
        user.attrs['user name'] = user_name
        
        sample = f.create_group('sample')
        sample.attrs['sample name'] = sample_name
        
        #dataroot = f['data']
        #dataTop = dataroot['single']
        dims = [dataTop['dim1'], dataTop['dim2']]
            
        #dset = dataTop['data']
        
        imageShape = data.shape[-2:]
        xdim = np.linspace(0,(imageShape[0]-1)*calX*1e9,imageShape[0]) #multiply by 1e9 for nanometers
        ydim = np.linspace(0,(imageShape[1]-1)*calY*1e9,imageShape[1])
        dims[-1][:] = xdim
        dims[-2][:] = ydim
        
        # Add as attribute so loading in Fiji provides pixel size
        # Note: Must be 3D so set the first element to 1
        fiji_element_size = (1, calY*1e6, calX*1e6)
        
        # Create dimension scales and attach them
        #for ii, d in enumerate(dims):
        #    d.make_scale(name=d.attrs['name'])
        #    dataTop.dims[ii].attach_scale(d)
        
        dset[:] = data
        
        # Create an attribute for easy loading into Fiji using HDF5 import
        dset.attrs['element_size_um'] = np.asarray(fiji_element_size).astype(np.float32)
        #print('Fiji attribute added = {}'.format(fiji_element_size))
                    
        # OR Write element size for simple Fiji loading (1, 1, y, x)
        # if len(dims) == 3:
        #    dset.attrs['element_size_um'] = (1.0, 
        #                                      self.calY*1e6, self.calX*1e6)
        # if len(dims) == 4:
        #    dset.attrs['element_size_um'] = (1.0, 1.0, 
        #                                     self.calY*1e6, self.calX*1e6)
        
        # Set the data as a valid EMD data set version 0.1
        dataTop.attrs['version_major'] = 0
        dataTop.attrs['version_minor'] = 1
        dataTop.attrs['emd_group_type'] = 1

@mcp.tool()
def calculate_optimal_defocus(
    convergence_angle:float,
    reciprocal_sampling:float,
    overlap:float = 85,
):
    """
    Calculates the optimal defocus and step size for a defocused
    ptychography 4D-STEM data set acquisition based on a
    given convergence angle and reciprocal sampling (sampling in 
    diffration space) for defocused ptychography and parallax.

    Parameters
    ----------
    convergence_angle : float
        specified in miliradians

    reciprocal sampling : float
        specified in inverse angstroms

    overlap : float [optional]
        overlap between adjacent probes in percent

    Returns
    -------
    : tuple, (float, float)
     A 2-tuple containing the optimal defocus in nm and the optimal step size in Angstrom
    """

    probe_box = 1/reciprocal_sampling

    optimal_probe_diameter = 1/3 * probe_box

    optimal_probe_radius = 1/2 * optimal_probe_diameter

    defocus_A = optimal_probe_radius/(convergence_angle/1000)

    defocus_nm = defocus_A/10

    step_size = (1-overlap/100) * optimal_probe_diameter
    
    return defocus_nm, step_size

@mcp.tool()
def team05_greet_me(username):
    """Function to say hello to a user who wants to control the team05"""
    return f'Hello {username}. Welcome to the TEAM0.5'

# Microscope (BEACON) server commands
@mcp.tool()
def acquire_ceos_tableau():
    """ Acquire a tableau. Hard coded to fast with 18 mrad."""
    d = {'type': 'tableau'}
    Response = microscope_client.send_traffic(d)
    if Response['reply_data'] is None:
        raise Exception('Command failed.')
    else:
        reply_data = Response['reply_data']
        return reply_data

@mcp.tool()        
def acquire_c1a1(WD_x=0.0, WD_y=0.0):
    """ Tilt and acquire a C1A1 measurement. WD is in mrad."""
    d = {'type': 'c1a1', 'ab_values':{'WD_x':WD_x, 'WD_y':WD_y}}
    Response = microscope_client.send_traffic(d)
    if Response['reply_data'] is None:
        raise Exception('Command failed.')
    else:
        reply_data = Response['reply_data']
        return reply_data

@mcp.tool()
def change_aberrations(ab_values:dict):
    '''
    Change aberrations relative to the current values by the indicated amount. 
    This is a delta from the current value.
    Aberrations are NOT reset to current values after function call.
    Some common names of the aberrations are:
    C1 is one-dimensional.
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
    Acquire HAADF-STEM image. A tuple is returned with information 
    about the image. The image is saved to disk as a Berkeley
    EMD file at the file path returned from this function.
    
    TODO: add dwell time to metadata!
    TODO: Use a dictionary to return and add contect to data returned
    
    Parameters
    ----------
    dwell : float
        Dwell time in seconds
    shape : tuple
        Image shape as a tuple. The first element is the width and
        the second element is the height
    
    Returns
    -------
    : tuple (str, float, float, string, float, float, float)
        The tuple is made of 7 elements. The description of the elements are 
        file path, (x pixel calibration, y pixel calibration, the calibration unit name,
        the image minimum, the image maximum, and the image standard deviation).
    '''
    
    offset = (0, 0) # hard coded for now
    d = {'type': 'image', 'dwell': dwell, 'shape': shape, 'offset': offset}
    Response = microscope_client.send_traffic(d)
    if Response is None:
        raise Exception('Command failed.')
    
    (image, calx, caly, cal_unit_name) = Response['reply_data']
    image_min = image.min()
    image_max = image.max()
    image_std = image.std()
    
    new_id = mfid.mfid()
    dir_path = Path('D:/user_data/Claude')
    file_path = dir_path / Path(f'{new_id[0]}.emd')
    write_emd_data(str(file_path), image, calx, caly, user_name='Claude', sample_name='')
    
    return (str(file_path), calx, caly, cal_unit_name, image_min, image_max, image_std)

def load_data(file_path):
    """Load an EMD data set from a file path"""
    pass

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
    if Response['reply_data'] is None:
        raise Exception('Command failed.')
    else:
        reply_data = Response['reply_data']
        return reply_data

@mcp.tool()
def get_convergence_angle():
    '''
    Get current STEM convergence angle in radians.

    Returns
    -------
    : float
        STEM convergence angle in radians.

    '''
    d = {'type': 'get_convergence_angle'}
    Response = microscope_client.send_traffic(d)
    if Response['reply_data'] is None:
        raise Exception('Command failed.')
    else:
        reply_data = Response['reply_data']
        print(reply_data)
        return reply_data

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
    if Response['reply_data'] is None:
        raise Exception('Command failed.')
    else:
        reply_data = Response['reply_data']
        return reply_data

@mcp.tool()
def get_camera_length():
    '''
    Get current STEM camera length. The camera length is in meters.
    This value should be treated as a uncalibrated "label." Converting
    it to a calibrated value is an extra step.

    Returns
    -------
    : float
        STEM camera length in meters.

    '''
    d = {'type': 'get_camera_length'}
    Response = microscope_client.send_traffic(d)
    if Response['reply_data'] is None:
        raise Exception('Command failed.')
    else:
        reply_data = Response['reply_data']
        return reply_data
   
@mcp.tool()
def get_camera_length_index():
    '''
    Get current STEM camera length index. It can be used to determine
    the actual camera length by indexing into the list of camera lenght
    names.
    
    Returns
    -------
    : float
        The STEM camera length index.

    '''
    d = {'type': 'get_camera_length_index'}
    Response = microscope_client.send_traffic(d)
    if Response['reply_data'] is None:
        raise Exception('Command failed.')
    else:
        reply_data = Response['reply_data']
        return reply_data

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
    None

    '''
    d = {'type': 'set_mag', 'mag': mag}
    microscope_client.send_traffic(d)

@mcp.tool()
def set_camera_length_index(CL_index:int):
    '''
    Set the STEM camera length index value.
    The names of several common index values are as follows:
    CL_index == 4 is 68 mm
    CL_index == 5 is 85 mm
    CL_index == 6 is 105 mm

    Parameters
    ----------
    CL_index : int
        Camera length index.

    Returns
    -------
    None

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
    terms of the pixelSize which is usually in meters.
    
    This function is used by centering for cross-correlation.
    
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

@mcp.tool()
def focus_stem_image(df_range:float=500e-9, num_seed_values:int=5,
                     num_samples:int=5, dwell_time:float=3e-6,
                     image_shape:tuple=(256, 256), noise_level:float=1e-4):
    '''
    Performs autofocusing using BEACON. This is a Bayesian optimization 
    routine which searches with the specified range for the best
    focus using the Upper Confidence Bound method. The best focus is 
    set on the microscope automatically.

    Parameters
    ----------
    df_range : float
        Maximum values plus and minus from the current defocus to 
        search. The range is in meters.
    num_seed_values : int
        The number of initial focus values to use to seed the surrogate model.
    num_samples : int
        The number of samples to acquire to estimate the optimal focus
    dwell_time : float
        The dwell time of the STEM images used in focusing. The dwell time is in
        seconds and a typical range of values is 1-10e-6 seconds.
    image_shape : tuple
        A tuple with two values that are the width and height of the STEM images
        to acquire at each focus. The standard deviation will be used in the Bayesian
        optimization routine. 
    noise_level : float
        The expected amount of noise in the image. A good estimate is the standard
        deviation of an image of the regiong to be used for focusing. Typical values are
        ~1e-4 for HAADF_STEM images and the value is unitless.
    
    
    Notes
    -----
    The image shape can be non-square. The width is the fast scan direction and the height
    is the slow scan direction. To speed things up is is recommneded to reduce the height. 
    Also, if doing tomography it is often advantageous to focusin the center of the image. 
    Reducing the height to 1/2 the width will acquire the image near the center.
    
    
    Returns
    -------
    : str
        A string that the focusing finished.

    '''
    range_dict = {'C1': [-df_range*1e9, df_range*1e9]} # convert to nanometers

    init_size_value = num_seed_values
    runs_value = num_samples
    dwell_value = dwell_time
    shape_value = image_shape
    noise_level = noise_level 
    
    metric_value = 'normvar'
    offset_value = (0, 0) # not used
    func_value = 'ucb' # always use upper confidence bound method
    return_images = True # this has to be True. Not sure why.
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
                          noise_level=noise_level)

    mm = beacon_client.model_max
    ab_keys = beacon_client.ab_keys
    ab_values = {}
    for i in range(len(ab_keys)):
        ab_values[ab_keys[i]] = mm[i] * 1e-9 # convert to meters

    beacon_client.ab_only(ab_values)
    print('Focusing finished.')

#@mcp.tool()
def focusing(df_range:float=500e-9):
    '''
    Performs autofocusing using BEACON. This is a Bayesian optimization 
    routine which searches with the specified range for the best
    focus. The best focus is set on the microscope automatically.
    The df_range is the focal range to serch in meters.
    
    DEPRECATED
    
    Parameters
    ----------
    df_range : float
        Maximum values plus and minus from the current defocus to 
        search. The default is 500e-9 meters.

    Returns
    -------
    : str
        A string that the focusing finished.

    '''
    print('call _focusing with df_range = {}'.format(df_range))
    _focusing(df_range)
    print('end focusing')
    return 'Focusing finished.'
    

def center_region(reference_image:npt.NDArray, max_distance:float=100e-9, ntries:int=4,
                  image_stage_cal_factor:float=1.0, dwell_search:float=2e-6, size_search:int=256):
    '''
    This acquires an image at the current stage position. It then calculates the cross-correlation
    between the reference image and the current image. The microscope moves the stage to center the
    region on the reference image and this continues iteratively. Either the object is centered 
    to within the max_distance tolerance or ntries is exceeded.
    
    Parameters
    ----------
    reference_image : numpy.ndarray
        Reference image to center on.
    max_distance : float, optional
        Maximum acceptable offset between actual and target position.
    ntries : int, optional
        Number of attempts to center the image.
    image_stage_cal_factor : float, optional
        Ratio of stage movement calibration to image resolution. The default is 1.0.
    dwell_search : float, optional
        Dwell time in seconds.
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
    cenetered = False
    for ii in range(ntries):
        
        curImage, pixelSize = acquire_image(dwell_search, size_search)
        
        offset = registration(reference_image, curImage, pixelSize) # Perform registration
        print(f'offset = {offset}') # for debugging
        dist = np.sqrt(offset[0]**2 + offset[1]**2)
        if dist > max_distance:
            # Move if needed
            # y may need -ve sign depending on which side of the horizontal axis it's on!!! Need to look into this!
            move_stage_delta(dX=offset[0]*image_stage_cal_factor, dY=offset[1]*image_stage_cal_factor) 
            time.sleep(1)
        else:
            print('Region centered on reference image')
            cenetered = True
            break
    
    if not centered:
        #d = {'type': 'close_column_valve'}
        #microscope_client.send_traffic(d)
        #print('Closing column valve')
        raise ValueError('Number of attempts to center has exceeded ntries.')

@mcp.tool()
def get_screenshot():
    '''
    Take a screenshot of the microscope GUI. The original PNG is saved on the 
    server side and a smaller JPG version is returned.
    
    Returns
    -------
    : fastmcp.utilities.types.Image
        The image as fastmcp Image from the utilities types module. 
        The format is a JPG.
    '''
    d = {'type': 'get_screenshot'}
    Response = microscope_client.send_traffic(d)
    
    image = Response['reply_data']
    image.save(r'd:\user_data\claude_image.png')
    original_width, original_height = image.size
    new_size = (original_width//2, original_height//2)
    resized_image = image.resize(new_size, resample=pilImage.LANCZOS)
    resized_image.save(r'd:\user_data\claude_image2.jpg')
    
    return mcpImage(r'd:\user_data\claude_image2.jpg')

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
    Get the accelerating voltage of the microscope
    
    Returns
    -------
    : float
        Accelerating voltage of the microscope in volts. This is also known as
        the high tension.
    
    '''
    d = {'type': 'get_voltage'}
    Response = microscope_client.send_traffic(d)
    if Response['reply_data'] is None:
        raise Exception('Command failed.')
    else:
        reply_data = Response['reply_data']
        return reply_data

@mcp.tool()
def get_stem_rotation_angle():
    '''
    Get the STEM scanning rotation angle. This is returned in radians.
    
    Returns
    -------
    : float
        The STEM scanning rotation angle in radisns
    
    '''
    d = {'type': 'get_stem_rotation_angle'}
    Response = microscope_client.send_traffic(d)
    if Response['reply_data'] is None:
        raise Exception('Command failed.')
    else:
        reply_data = Response['reply_data']
        return reply_data

@mcp.tool()
def set_stem_rotation_angle(rotation_angle:float=0.0):
    '''
    Set the STEM scanning rotation angle in radians.
    
    Returns
    -------
    : str
        A response telling you the command succeeded
    
    '''
    d = {'type': 'set_stem_rotation_angle', 'stem_rotation_angle':rotation_angle}
    Response = microscope_client.send_traffic(d)
    reply_message = Response['reply_message']
    return reply_message

@mcp.tool()
def get_defocus():
    '''
    Get the defocus of the microscope
    
    Returns
    -------
    : float
        Current defocus value of the microscope in meters.
    
    '''
    d = {'type': 'get_defocus'}
    Response = microscope_client.send_traffic(d)
    if Response['reply_data'] is None:
        raise Exception('Command failed.')
    else:
        reply_data = Response['reply_data']
        return reply_data

@mcp.tool()
def set_defocus(target_df:float=0e-9):
    '''
    Set the defocus of the microscope in meters.
    
    Returns
    -------
    defocus: float.
        Current defocus value of the microscope in metres
    
    '''
    d = {'type': 'set_defocus', 'target_df': target_df}
    Response = microscope_client.send_traffic(d)
    df = Response['reply_message']
    return df

###
# Gatan server commands
###
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
def acquire_4D_scan(width:int, height:int, scan_rotation:float, nread:int):
    '''
    Acquire a 4D-STEM scan. This takes a data set using the 4D Camera.
    The dwell time per probe position is always 11e-6 seconds.
    
    Ensure you wait a sufficient amount of time for the data to offload
    or stream to NERSC before calling this again.
    
    Parameters
    ----------
    height : int
     The height in pixels of the 4D-STEM scan.
    width : int
     The width in pixels of the 4D-STEM scan.
    scan_rotation : float
     The STEM scan rotation in degrees.
    nread : int
     The number of 4D Camera frames to acquire at each probe position.
     
    Returns
    -------
    None.
    
    '''
    params = {'pwidth':width, 'pheight':height, 'rotation':scan_rotation, 'nread':nread}
    gatan_client.send_traffic(('set_gatan', 0)) # set gatan for 4D scan
    gatan_client.send_traffic(('acquire_4dcamera_scan', params))
    gatan_client.send_traffic(('set_tia', 0)) # set back to TIA control

@mcp.tool()
def acquire_haadf_dm(dwell_time:float, width:int, height:int, scan_rotation:float, signal_index:int):
    '''
    Acquire a STEM image using DigitalMicrograph. The TEAM 0.5 only has a HAADF detector such 
    that the signal_index can only be set to 0.
    
    Parameters
    ----------
    dwell_time : float
     The dwell time for each probe position in seconds.
    height : int
     The height in pixels of the STEM image along the fast direction.
    width : int
     The width in pixels of the STEM image along the slow direction.
    scan_rotation : float
     The STEM scan rotation in degrees.
    signal_index : int
     The index value of the desired detector. On TEAM 0.5 this can only be == 0
     
    Returns
    -------
    None.
    
    '''
    params = {'pwidth':width, 'pheight':height, 'rotation':scan_rotation, 'nread':nread}
    gatan_client.send_traffic(('set_gatan', 0)) # set gatan for 4D scan
    gatan_client.send_traffic(('acquire_stem_scan', params))
    gatan_client.send_traffic(('set_tia', 0)) # set back to TIA control

class Microscope_Client():
    '''Communicates with the server on the microscope PC.'''
    def __init__(self, host='192.168.0.24', port=7001):
        try:
            # Set timeout in milliseconds
            timeout_ms = 50000  # 5 seconds
            context = zmq.Context()
            self.ClientSocket = context.socket(zmq.REQ)
            self.ClientSocket.setsockopt(zmq.RCVTIMEO, timeout_ms)
            self.ClientSocket.setsockopt(zmq.SNDTIMEO, timeout_ms)
            self.ClientSocket.connect(f"tcp://{host}:{port}")
        except ConnectionRefusedError:
            print('Please start the BEACON server and try again...')
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
        : dict or None
            Response from the server. If no repsonse then None.
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
    """Communicates with the server on the Gatan PC. This is currently called
    the multiscan server because it was used to take multiple 4D-STEM scans. 
    We will rename this to a more generic name in the future."""
    def __init__(self, host='192.168.0.30', port=13579):
        try:
            # Set timeout in milliseconds
            timeout_ms = 50000  # 5 seconds
            context = zmq.Context()
            self.ClientSocket = context.socket(zmq.REQ)
            self.ClientSocket.setsockopt(zmq.RCVTIMEO, timeout_ms)
            self.ClientSocket.setsockopt(zmq.SNDTIMEO, timeout_ms)
            self.ClientSocket.connect(f"tcp://{host}:{port}")
            print('Connected')
        except ConnectionRefusedError:
            print('Please start the Gatan (multiscan) server and try again...')
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
        : dict or None
            Response from the server. If no repsonse then None.
        '''
        print(f'Gatan_Client: {message}')
        try:
            self.ClientSocket.send(pickle.dumps(message))
            response = pickle.loads(self.ClientSocket.recv())
            return response
        except zmq.Again:
            print("Timeout occurred.")
            return None

if __name__ == "__main__":
    # TEAM 0.5 microscope PC connection settings
    mhost = '192.168.0.24'
    mport = 7001
    
    microscope_client = Microscope_Client(mhost, mport) # Communicate with microscope PC
    
    beacon_client = BEACON_Client(mhost, mport) # Communicate with BEACON on the microscope PC

    # Check the connection
    d = {'type': 'ping'}
    Response = microscope_client.send_traffic(d)
    print(Response['reply_message'])

    # Gatan PC connection settings
    ghost = '192.168.0.30'
    gport = 13579
    
    gatan_client = Gatan_Client(ghost, gport) # communicates with the Gatan PC

    #print('Note: MCP run command commented out.') # for testing
    mcp.run(transport = "sse", host = "team05-support.dhcp.lbl.gov", port = 8080)
    