# -*- coding: utf-8 -*-
"""
Created on Tue Oct  8 14:10:26 2024

@author: alexa
"""

import sys
import pickle
import zmq
import ncempy.io as nio
import os
from subprocess import call
import time
import dm_script
import mb_script

sys.path.append('C:/Users/VALUEDGATANCUSTOMER/Documents/Maestro')
from TEAM05_tia_gatan import set_TIA2, set_Gatan  # might need to set path to library

class Multiscan_Server():
    def __init__(self):
        
        self.SIM = False
        self.is_gatan = False
        
        if self.SIM:
            self.DMSCRIPT = r'4Dcamera_automation_acquireScan_temp.s'
            self.dm4_filename = 'latest_4Dscan.dm4'
            self.dm4_filename_copy = 'latest_4Dscan.dm4'
            self.MBSCRIPT = r'move_beam.s'
        else:
            self.DMSCRIPT = r'C:\Users\VALUEDGATANCUSTOMER\Documents\automation\4Dcamera_automation_acquireScan_temp.s'
            self.dm4_filename = 'C:/Users/VALUEDGATANCUSTOMER/Documents/automation/latest_4Dscan.dm4'
            self.dm4_filename_copy = 'C:/Users/VALUEDGATANCUSTOMER/Documents/automation/latest_4Dscan_copy.dm4'
            self.MBSCRIPT = r'C:\Users\VALUEDGATANCUSTOMER\Documents\automation\move_beam.s'
        
        port = 13579
        
        context = zmq.Context()
        self.serverSocket = context.socket(zmq.REP)
        self.serverSocket.bind('tcp://*:'+str(port))
        print('Server Online')

        while True:
            
            data = self.serverSocket.recv()
            upd = pickle.loads(data)
            
            message = None
            
            print(upd[0])
            
            if upd[0] == 'tia_or_gatan':
                message = ('is_gatan', self.is_gatan)
            elif upd[0] == 'set_gatan':
                self.is_gatan = self.set_is_gatan(True)
                message = ('is_gatan', self.is_gatan)
            elif upd[0] == 'set_tia':
                self.is_gatan = self.set_is_gatan(False)
                message = ('is_gatan', self.is_gatan)
            elif upd[0] == 'take_and_return_data':
                prev_is_gatan = self.is_gatan
                if not self.is_gatan:
                    self.is_gatan = self.set_is_gatan(True)
                ret = self.take_gatan_data(upd[1])
                if self.is_gatan != prev_is_gatan:
                    self.is_gatan = self.set_is_gatan(prev_is_gatan)
                #message = ('gatan_is_busy', False)
                message = ('gatan_data', ret)
            elif upd[0] == 'set_roi':
                roi = upd[1]
                message = ('set_roi', roi)
            elif upd[0] == 'move_beam':
                print(upd[1][0], upd[1][1])
                self.move_beam(upd[1][0], upd[1][1])
                message = ('beam moved', 0)
            elif upd[0] == 'get_pixel_size':
                ps = self.get_pixel_size(nn)
                message = ('pixelSize', ps)
            else:
                print(f'unknown command: {upd}')

            self.serverSocket.send(pickle.dumps(message))
            print("Idle")
    
    def get_pixel_size(nn):
        return nio.dm.dmReader(f'X:/scan{nn}')['calX']
    
    def move_beam(self, dX, dY):
        mbs = mb_script.move_beam_dm(dX, dY)
        print('writing move beam script')
        with open(self.MBSCRIPT, 'w') as f:
            f.write(mbs)
        if not self.SIM:
            # call script
            print('calling move beam script')
            with open('NUL', 'w') as _:
                call(f'\"C:\\Program Files\\Gatan\\DigitalMicrograph.exe\" /ef \"{self.MBSCRIPT}\"')
        
    def take_gatan_data(self, p):
        self.call4DCamDMscript(p)
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

    def call4DCamDMscript(self, paramdict):
        try:
            params = {'ptime': 11e-6, 'pwidth': 512, 'pheight': 512, 'emd':None}
            if isinstance(paramdict, dict):
                params.update(paramdict)
            if params['emd'] is None:
                params['emd'] = "no emd file"
            dms = dm_script.dynamic_dm_script(ptime=params['ptime'], pwidth=params['pwidth'], pheight=params['pheight'], emd=params['emd'])
            print('writing DM script')
            with open(self.DMSCRIPT, 'w') as f:
                f.write(dms)
            if not self.SIM:
                # delete any previous dm4 files
                if os.path.exists(self.dm4_filename):
                    os.remove(self.dm4_filename)
                if os.path.exists(self.dm4_filename_copy):
                    os.remove(self.dm4_filename_copy)
                # call script
                print('calling DM script')
                with open('NUL', 'w') as _:
                    call(f'\"C:\\Program Files\\Gatan\\DigitalMicrograph.exe\" /ef \"{self.DMSCRIPT}\"')
                # wait for dm4 file to appear
                while not os.path.exists(self.dm4_filename_copy):
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
    ms = Multiscan_Server()