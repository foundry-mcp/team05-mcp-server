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

import dm_scripts

# Impor the functions for the TIA/Gatan robot
sys.path.append('C:/Users/VALUEDGATANCUSTOMER/Documents/Maestro')
from TEAM05_tia_gatan import set_TIA2, set_Gatan  # might need to set path to library

class GatanServer():
    def __init__(self, sim=False, port=13579):
        
        self.SIM = sim # indicate simulation mode
        self.is_gatan = False # start with robot in TIA position

        # The path where the dm scripts will be written
        self.dir_path = Path('C:/Users/VALUEDGATANCUSTOMER/Documents/automation/')
        
        if self.SIM:
            self.DMSCRIPT = '4Dcamera_automation_acquireScan_temp.s'
            self.dm4_filename = 'latest_4Dscan.dm4'
            self.MBSCRIPT = 'move_beam.s'
        else:
            self.DMSCRIPT = self.dir_path / Path('4Dcamera_automation_acquireScan_temp.s')
            self.dm4_filename = self.dir_path / Path('latest_4Dscan.dm4')
            self.MBSCRIPT = self.dir_path / Path('move_beam.s')
        
        context = zmq.Context()
        self.serverSocket = context.socket(zmq.REP)
        self.serverSocket.bind('tcp://*:'+str(port))
        print('Server Online')

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
            elif command == 'take_and_return_data':
                # Acquire 4D STEM data
                prev_is_gatan = self.is_gatan
                if not self.is_gatan:
                    self.is_gatan = self.set_is_gatan(True)
                ret = self.take_4dstem_data(params)
                if self.is_gatan != prev_is_gatan:
                    self.is_gatan = self.set_is_gatan(prev_is_gatan)
                message = ('gatan_data', ret)
            elif command == 'acquire_stem_scan':
                # Acquire HAADF-STEM data
                prev_is_gatan = self.is_gatan
                if not self.is_gatan:
                    self.is_gatan = self.set_is_gatan(True)
                ret = self.take_gatan_data(params)
                if self.is_gatan != prev_is_gatan:
                    self.is_gatan = self.set_is_gatan(prev_is_gatan)
                #message = ('gatan_is_busy', False)
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
            The distance to move the beam in the fast scan direction. In pixels or real values?
        dY : float
            The distance to move the beam in the slow scan direction. In pixels or real values?
        """
        mbs = dm_scripts.move_beam_dm(dX, dY)
        print('writing move beam script')
        with open(self.MBSCRIPT, 'w') as f:
            f.write(mbs)
        if not self.SIM:
            # call script
            print('calling move beam script')
            with open('NUL', 'w') as _:
                call(f'\"C:\\Program Files\\Gatan\\DigitalMicrograph.exe\" /ef \"{self.MBSCRIPT}\"')
        
    def take_stem_data(self, p):
        """Acquires a HAADF-STEM image"""
        self.call_stem_script(p)
        
        dm4_file = nio.dm.dmReader(self.dm4_filename)
        data = dm4_file['data']
        with nio.dm.fileDM(self.dm4_filename) as f1:
            allTags = f1.allTags
        params = {'alltags': allTags,
                  'calX': allTags.get('.ImageList.2.ImageData.Calibrations.Dimension.1.Scale', 1)*1e-6,
                  'calY': allTags.get('.ImageList.2.ImageData.Calibrations.Dimension.2.Scale', 1)*1e-6,
                  '4Dscan number': allTags.get('.ImageList.2.ImageTags.4Dcamera Parameters.scan_number', None),
                  'dwell': allTags.get('.ImageList.2.ImageTags.DigiScan.Sample Time', 0)*1e-6
                  }
        print("HAADF data shape = {}".format(data.shape))
        return data, params

    def call_stem_script(self, paramdict):
        """ Acquires a STEM datset"""
        try:
            params = {'ptime': 11e-6, 'pwidth': 512, 'pheight': 512, 'rotation':0, 'nread':1}
            if isinstance(paramdict, dict):
                params.update(paramdict)
            dms = dm_script.dynamic_dm_script(pwidth=params['pwidth'], pheight=params['pheight'], 
                                              rotation=params['rotation'], nread=params['nread'])
            print('writing DM script')
            with open(self.DMSCRIPT, 'w') as f:
                f.write(dms)
            if not self.SIM:
                # delete any previous dm4 files
                if os.path.exists(self.dm4_filename):
                    os.remove(self.dm4_filename)
                # call script
                print('calling DM script')
                with open('NUL', 'w') as _:
                    call(f'\"C:\\Program Files\\Gatan\\DigitalMicrograph.exe\" /ef \"{self.DMSCRIPT}\"')
                # wait for dm4 file to appear
                while not self.dm4_filename.exists():
                    time.sleep(0.1)
                print('done')
        except:
            raise
    
    def take_4dstem_data(self, p):
        """Acquires a HAADF-STEM image"""
        self.call_4DCam_script(p)
        dm4_file = nio.dm.dmReader(self.dm4_filename)
        data = dm4_file['data']
        with nio.dm.fileDM(self.dm4_filename) as f1:
            allTags = f1.allTags
        params = {'alltags': allTags,
                  'calX': allTags.get('.ImageList.2.ImageData.Calibrations.Dimension.1.Scale', 1)*1e-6,
                  'calY': allTags.get('.ImageList.2.ImageData.Calibrations.Dimension.2.Scale', 1)*1e-6,
                  '4Dscan number': allTags.get('.ImageList.2.ImageTags.4Dcamera Parameters.scan_number', None),
                  'dwell': allTags.get('.ImageList.2.ImageTags.DigiScan.Sample Time', 0)*1e-6
                  }
        print("HAADF data shape = {}".format(data.shape))
        return data, params
    
    def call_4DCam_script(self, paramdict):
        """ Acquires a 4D Camera datset"""
        try:
            params = {'ptime': 11e-6, 'pwidth': 512, 'pheight': 512, 'rotation':0, 'nread':1}
            if isinstance(paramdict, dict):
                params.update(paramdict)
            dms = dm_script.dynamic_dm_script(pwidth=params['pwidth'], pheight=params['pheight'], 
                                              rotation=params['rotation'], nread=params['nread'])
            print('writing DM script')
            with open(self.DMSCRIPT, 'w') as f:
                f.write(dms)
            if not self.SIM:
                # delete any previous dm4 files
                if os.path.exists(self.dm4_filename):
                    os.remove(self.dm4_filename)
                # call script
                print('calling DM script')
                with open('NUL', 'w') as _:
                    call(f'\"C:\\Program Files\\Gatan\\DigitalMicrograph.exe\" /ef \"{self.DMSCRIPT}\"')
                # wait for dm4 file to appear
                while not self.dm4_filename.exists():
                    time.sleep(0.1)
                print('done')
        except:
            raise

    def set_is_gatan(self, ig):
        if not self.SIM:
            if ig:
                set_Gatan()
            else:
                set_TIA2()
            return ig
        else:
            return ig

if __name__ == '__main__':
    ms = GatanServer()