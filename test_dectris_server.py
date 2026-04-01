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

from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Optional


class Dectris_Client():
    """Communicates with the server"""
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
        print(f'Dectris_Client: {message}')
        try:
            self.ClientSocket.send(pickle.dumps(message))
            response = pickle.loads(self.ClientSocket.recv())
            return response
        except zmq.Again:
            print("Timeout occurred.")
            return None
            
if __name__ == "__main__":

    # Dectris connection settings
    ghost = '192.168.0.77'
    gport = 13580
    
    dectris_client = Dectris_Client(ghost, gport) # communicates with the Gatan PC
    params = {'file_write_mode':'h5'}
    dectris_client.send_traffic(('setup_detector', params))
    dectris_client.send_traffic(('acquire_scan', 0)) 