# -*- coding: utf-8 -*-
"""
A zmq server that writes Gatan DigitalMicrograph scripts
to disk and executes them through a system call to 
DigitalMicrograph.exe.
"""

import sys
from pathlib import Path
import pickle
import zmq
import ncempy.io as nio
import os
from subprocess import call
import time
import json

import dm_scripts

class GatanServer():
    def __init__(self, sim=False, port=13579):
        
        self.SIM = sim # indicate simulation mode
        
        # The path where the dm scripts will be written
        self.dir_path = Path('C:/Users/VALUEDGATANCUSTOMER/Documents/automation/')
        
        if self.SIM:
            self.DMSCRIPT = '4Dcamera_automation_acquireScan_temp.s'
            self.dm4_filename = 'latest_4Dscan.dm4'
            self.haadf_filename = 'latest_haadf.dm4'
            self.MBSCRIPT = 'move_beam.s'
        else:
            self.DMSCRIPT = self.dir_path / Path('4Dcamera_automation_acquireScan_temp.s')
            self.dm4_filename = self.dir_path / Path('latest_4Dscan.dm4')
            self.haadf_filename = self.dir_path / 'latest_haadf.dm4'
            self.MBSCRIPT = self.dir_path / Path('move_beam.s')
        
        # Create button pusher client
        button_pusher_context = zmq.Context()
        self.button_pusher_socket = button_pusher_context.socket(zmq.REQ)
        self.button_pusher_socket.connect("tcp://localhost:5555")
        
        # Create server
        context = zmq.Context()
        self.serverSocket = context.socket(zmq.REP)
        self.serverSocket.bind('tcp://*:'+str(port))
        print('Server Online')
        
        # start with TIA
        self.send_command(self.button_pusher_socket, {"action": "set_TIA2"})
        self.is_gatan = False 
        
        while True:
            
            data = self.serverSocket.recv()
            command, params = pickle.loads(data)
            
            message = None
            
            print(f'received command: {command}')
            
            if command == 'tia_or_gatan':
                message = ('is_gatan', self.is_gatan)
            elif command == 'set_gatan':
                self.is_gatan = self.set_is_gatan(True)
                message = ('is_gatan', self.is_gatan)
            elif command == 'set_tia':
                self.is_gatan = self.set_is_gatan(False)
                message = ('is_gatan', self.is_gatan)
            elif command == 'acquire_4dcamera_scan':
                # Acquire 4D STEM data
                prev_is_gatan = self.is_gatan
                if not self.is_gatan:
                    self.is_gatan = self.set_is_gatan(True)
                ret = self.acquire_4dcamera_scan(params)
                if self.is_gatan != prev_is_gatan:
                    self.is_gatan = self.set_is_gatan(prev_is_gatan)
                message = ('gatan_data', ret)
            elif command == 'acquire_stem_scan':
                # Acquire HAADF-STEM data
                prev_is_gatan = self.is_gatan
                if not self.is_gatan:
                    self.is_gatan = self.set_is_gatan(True)
                print('HI')
                print(params)
                ret = self.acquire_stem_scan(params)
                if self.is_gatan != prev_is_gatan:
                    self.is_gatan = self.set_is_gatan(prev_is_gatan)
                message = ('gatan_data', ret)
            elif command == 'set_roi':
                roi = params
                message = ('set_roi', roi)
            elif command == 'move_beam':
                print(params[0], params[1])
                self.move_beam(params[0], params[1])
                message = ('beam moved', 0)
            elif command == 'get_pixel_size':
                ps = self.get_pixel_size(nn)
                message = ('pixelSize', ps)
            else:
                print(f'unknown command: {upd}')

            self.serverSocket.send(pickle.dumps(message))
            print("Idle")
    
    def get_pixel_size(nn):
        """Reads the file on disk to get the pixel size"""
        return nio.dm.dmReader(f'X:/scan{nn}')['calX']
    
    def move_beam(self, dX, dY):
        """Moves the beam. This is usually used for "crater" datasets
        where the sample drifts
        
        dX : float
            The distance to move the beam in the fast scan direction in pixels.
        dY : float
            The distance to move the beam in the slow scan direction in pixels.
        """
        mbs = dm_scripts.move_beam_script(dX, dY)
        print('writing move beam script')
        with open(self.MBSCRIPT, 'w') as f:
            f.write(mbs)
        if not self.SIM:
            # call script
            print('calling move beam script')
            with open('NUL', 'w') as _:
                call(f'\"C:\\Program Files\\Gatan\\DigitalMicrograph.exe\" /ef \"{self.MBSCRIPT}\"')
        
    def acquire_stem_scan(self, params):
        """Acquires a HAADF-STEM image
        
        Parameters
        ----------
        params : dict
            The parameter dictionary for acquiring a 4D-STEM dataset with the 4D Camera.
            It requires dwell_time, width, height, rotation, and signal_index keys.

        Returns
        -------
        : tuple
            A tuple containing the STEM data as a numpy array and metadata as a tuple.
        """
        self.call_stem_script(params)
        
        dm4_file = nio.dm.dmReader(self.haadf_filename)
        data = dm4_file['data']
        with nio.dm.fileDM(self.haadf_filename) as f1:
            allTags = f1.allTags
        metadata = {'alltags': allTags,
                  'calX': allTags.get('.ImageList.2.ImageData.Calibrations.Dimension.1.Scale', 1)*1e-6,
                  'calY': allTags.get('.ImageList.2.ImageData.Calibrations.Dimension.2.Scale', 1)*1e-6,
                  'units': allTags.get('.ImageList.2.ImageData.Calibrations.Dimension.1.Units', ''),
                  'dwell': allTags.get('.ImageList.2.ImageTags.DigiScan.Sample Time', 0)*1e-6
                  }
        print("HAADF data shape = {}".format(data.shape))
        return data, metadata

    def call_stem_script(self, params):
        """ Acquires a STEM datset"""
        try:
            dms = dm_scripts.acquire_stem_script(dwell_time=params['dwell_time'],
                                                pwidth=params['pwidth'], pheight=params['pheight'], 
                                                rotation=params['rotation'], signal_index=params['signal_index'])
            print('writing DM script')
            with open(self.DMSCRIPT, 'w') as f:
                f.write(dms)

            # call script
            print('calling DM script')
            with open('NUL', 'w') as _:
                call(f'\"C:\\Program Files\\Gatan\\DigitalMicrograph.exe\" /ef \"{self.DMSCRIPT}\"')
            print('haadf scan finished')
        except:
            raise
    
    def acquire_4dcamera_scan(self, params):
        """Acquires a 4D-STEM dataset.

        Parameters
        ----------
        params : dict
            The parameter dictionary for acquiring a 4D-STEM dataset with the 4D Camera.
            It requires pwidth, pheight, nread, and rotation keys.
        
        """
        # Acquire the data
        self.call_4DCam_script(params)
        # Read the dm4 file
        dm4_file = nio.dm.dmReader(self.dm4_filename)
        data = dm4_file['data']
        # read the dm4 metadata
        with nio.dm.fileDM(self.dm4_filename) as f1:
            allTags = f1.allTags
        metadata = {'alltags': allTags,
                   'calX': allTags.get('.ImageList.2.ImageData.Calibrations.Dimension.1.Scale', 1)*1e-6,
                   'calY': allTags.get('.ImageList.2.ImageData.Calibrations.Dimension.2.Scale', 1)*1e-6,
                   '4Dscan number': allTags.get('.ImageList.2.ImageTags.4Dcamera Parameters.scan_number', None),
                   'dwell': allTags.get('.ImageList.2.ImageTags.DigiScan.Sample Time', 0)*1e-6
                   }
        
        return data, metadata
    
    def call_4DCam_script(self, params):
        """ Acquires a 4D Camera datset

        Parameters
        ----------
        params : dict
            The parameter dictionary for acquiring a 4D-STEM dataset with the 4D Camera.
            It requires pwidth, pheight, nread, and rotation keys.
        
        Returns
        -------
        : tuple
            A tuple containing the STEM data as a numpy array and metadata as a tuple.
        """
        try:
            dms = dm_script.dynamic_dm_script(pwidth=params['pwidth'], pheight=params['pheight'], 
                                              rotation=params['rotation'], nread=params['nread'])
            print('writing DM script')
            with open(self.DMSCRIPT, 'w') as f:
                f.write(dms)

            # call script
            print('calling DM script')
            with open('NUL', 'w') as _:
                call(f'\"C:\\Program Files\\Gatan\\DigitalMicrograph.exe\" /ef \"{self.DMSCRIPT}\"')
            print('done')
        except:
            raise

    def set_is_gatan(self, push_gatan):
        """
        This sends a message to the button pusher to push the Gatan button
        or the TIA button.
        """
        if not self.SIM:
            if push_gatan:
                self.send_command(self.button_pusher_socket, {"action": "set_Gatan"})
            else:
                self.send_command(self.button_pusher_socket, {"action": "set_TIA2"})
            return push_gatan
        else:
            return push_gatan
    
    def send_command(self, soc, command):
        """Send a command to the button pusher and print the response"""
        print(f"\n>>> Sending: {command}")
        soc.send_string(json.dumps(command))
        response = json.loads(soc.recv_string())
        print(f"<<< Response: {response}")
        return response
    
if __name__ == '__main__':
    ms = GatanServer()
