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

class Gatan_Client():
    """Communicates with the server on the Gatan PC. This is currently called
    the multiscan server because it was used to take multiple 4D-STEM scans. 
    We will rename this to a more generic name in the future."""
    def __init__(self, host='192.168.0.30', port=13579):
        try:
            # Set timeout in milliseconds
            timeout_ms = 5000  # 5 seconds
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

    # Gatan PC connection settings
    ghost = '192.168.0.30'
    gport = 13579
    
    gatan_client = Gatan_Client(ghost, gport) # communicates with the Gatan PC
    
    # Test DM HAADF acquire
    #params = {'pwidth':512, 'pheight':512, 'rotation':0, 'dwell_time':1e-6,'signal_index':0}
    #gatan_client.send_traffic(('set_gatan', 0)) # set gatan for 4D scan
    #response = gatan_client.send_traffic(('acquire_stem_scan', params))
    #print(response)
    #gatan_client.send_traffic(('set_tia', 0)) # set back to TIA control
    
    # Test 4D acquire
    params = {'pwidth':128, 'pheight':128, 'rotation':0, 'nread':2}
    #gatan_client.send_traffic(('set_gatan', 0)) # set gatan for 4D scan
    response = gatan_client.send_traffic(('acquire_4dcamera_scan', params))
    print(response)
    #gatan_client.send_traffic(('set_tia', 0)) # set back to TIA control