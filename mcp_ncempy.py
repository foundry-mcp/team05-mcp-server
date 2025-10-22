# -*- coding: utf-8 -*-
"""
Test MCP agent that can load, process, and display data

@author: Peter Ercius
"""

from pathlib import Path
import multiprocessing as mp

from fastmcp import FastMCP
from datetime import datetime, timedelta
from typing import Any, Optional

import requests
from pydantic import AnyHttpUrl, BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from requests.exceptions import HTTPError, RequestException

import ncempy
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm, NoNorm
import mfid

data = {} # a dictionary that holds all the data.

mcp = FastMCP("NCEMPY MCP")

class ProcessPlotter:
    """ Creates a plot on the MCP server side that can
    show images and be updated dynamically. """
    def __init__(self):
        self.pipe, plotter_pipe = mp.Pipe()
        self.plot_process = mp.Process(target=self._plot_process, args=(plotter_pipe,))
        self.plot_process.start()
        
        
    def _plot_process(self, pipe):
        self.fig, self.ax = plt.subplots()
        self.ax.set_title("Dynamic Plot")
        plt.show(block=False) # Non-blocking show

        while True:
            if pipe.poll(): # Check for incoming data
                data = pipe.recv()
                if data is None: # Signal to close
                    plt.close(self.fig)
                    break
                self.ax.clear()
                image = data[0]
                norm = data[1]
                self.ax.imshow(image, norm=norm)
                self.fig.canvas.draw()
                self.fig.canvas.flush_events() # Update the display

            plt.pause(0.01) # Small pause to allow events to process

    def plot(self, data):
        self.pipe.send(data)

    def close(self):
        self.pipe.send(None) # Send signal to close the plot

@mcp.tool()
def test_this_server(from_llm:str):
    """THis tool simply prints what the LLM sends
    
    Parameters
    ----------
    from_llm : str
    The string to print
    """
    print(from_llm)

@mcp.tool()
def load_image(directory:str, file_name:str):
    """A function that reads a file using ncempy. The data
    stays on the server and is stored in a dictionary. Each data set
    can then be accessed using a key. This key is returned when the
    file is loaded.
    
    Parameters
    ----------
    directory : str
    The directory where the data is located
    file_name : str
    The name of the file to load.
    
    Returns
    -------
    : str
    The file_id of the file which is a key used to access the data later.
    """
    file_path = Path(directory) / Path(file_name)
    print(file_path)
    dd = ncempy.read(file_path)
    file_id = new_id = mfid.mfid()
    data[file_id[0]] = dd
    return file_id[0]

@mcp.tool()
def list_data_files(directory:str):
    """A function that lists the data files available on the server
    in the directory indicated.
    
    Parameters
    ----------
    directory : str
    The directory where the data is located
    
    Returns
    -------
    : list
    A list of full file paths as strings.
    """
    dir_path = Path(directory)
    return [str(ii) for ii in dir_path.glob('*.*')]

@mcp.tool()
def get_statistics(file_id:str):
    """Caclulates the statistics of the image intensities.
    
    Parameters
    ----------
    file_id : str
    The file_id to use to access the data
    
    Returns
    -------
    : tuple
    A tuple with the maximum, minumum, and standard deviation as floats
    """
    dd = data[file_id]
    mm = (dd['data'].max(), dd['data'].min(), dd['data'].std())
    return mm

@mcp.tool()
def plot_data(file_id:str):
    """This uses matplotlib imshow to plot the data.
    This will show up on the server only.
    
    Parameters
    ----------
    file_id : str
    The file_id to use to access the data
    """
    print('plotting')
    image = data[file_id]['data']
    norm = 'linear'
    plotter.plot((image, norm))

@mcp.tool()
def plot_data_fft(file_id:str):
    """This uses matplotlib imshow to plot the 
    fast fourier transform (FFT) of the data.
    This will show up on the server only.
    
    Parameters
    ----------
    file_id : str
    The file_id to use to access the data
    """
    print('plotting fft')
    image = np.abs(np.fft.fftshift(np.fft.fft2(data[file_id]['data'])))
    norm = 'log'
    plotter.plot((image, norm))
    

@mcp.tool()
def get_loaded_data():
    """Returns all of the file ids for all loaded data.
    
    Returns
    -------
    : list
    """
    return [kk for kk in data.keys()]

@mcp.tool()
def get_emd_metadata(directory:str, file_name:str):
    """Returns the metadata for a data set 
    that is in the Berkeley EMD format.
    
    Parameters
    ----------
    directory : str
    The directory where the data is located
    file_name : str
    The name of the file from which to load the metadata.
    
    Returns
    -------
    : dict
    A dictionary with various metadata
    """
    file_path = Path(directory) / Path(file_name)
    md = {}
    with ncempy.io.emd.fileEMD(file_path) as f0:
        md.update(f0.microscope.attrs)
        md.update(f0.sample.attrs)
        md.update(f0.user.attrs)
        
        # Get the pixel size and unit
        try:
            dims = f0.get_emddims(f0.list_emds[0])
            pixel_size_y = dims[0][0][1] - dims[0][0][0]
            pixel_size_x = dims[1][0][1] - dims[1][0][0]
            
            md['pixel_size_y'] = pixel_size_y
            md['pixel_size_x'] = pixel_size_x
            md['dimension_y_name'] = dims[0][1].replace('_', '')
            md['dimension_x_name'] = dims[1][1].replace('_', '')
            md['pixel_size_y_unit'] = dims[1][2].replace('_', '')
            md['pixel_size_x_unit'] = dims[1][2].replace('_', '')
        except:
            print('cant get pixel size')
            raise
        
    return md
    
@mcp.tool()
def get_dm_metadata(directory:str, file_name:str, num=0):
    """Returns the metadata for a data set 
    that is in the Gatan DM3 or DM4 format.
    
    Only simple file
    
    Parameters
    ----------
    directory : str
    The directory where the data is located
    file_name : str
    The name of the file from which to load the metadata.
    num: int, optional
    The number of the dataset in the file. Usually only 1 dataset is in the file
    
    Returns
    -------
    : dict
    A dictionary with various metadata
    """
    file_path = Path(directory) / Path(file_name)
    with ncempy.io.dm.fileDM(file_path) as f0:
        md = f0.getMetadata(0)
    return md

@mcp.tool()
def delete_data_in_memory():
    """This frees all data in memory."""
    data = {}

if __name__ == "__main__":
    
    # A dynamic matplotlib plotter
    # This allows the server side to show data as images
    plotter = ProcessPlotter()
    
    mcp.run(transport="sse", host="127.0.0.1", port=8082)
    # mcp.run(transport = "sse", host = "team05-support.dhcp.lbl.gov", port=8082)