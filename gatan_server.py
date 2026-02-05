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
import logging
import traceback
import argparse

import dm_scripts

class GatanServer():
    def __init__(self, sim=False, port=13579):
        """A server that accepts commands to control Gatan DigitalMicrograph.

        Parameters
        ----------
        sim : bool
            If True, simulation mode is enabled (no actual DM scripts executed).
        port : int
            The port to open for the server. The server will bind that port
            on all available interfaces.
        """
        # Setup logging
        self.logger = logging.getLogger('GatanServer')
        self.logger.setLevel(logging.DEBUG)

        # Create formatters
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # File handler
        file_handler = logging.FileHandler('gatan_server.log')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

        self.logger.info('Initializing GatanServer')

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
        self.logger.info('Server Online on port {}'.format(port))

        # start with TIA
        self.send_command(self.button_pusher_socket, {"action": "set_TIA2"})
        self.is_gatan = False

        # Command dispatch dictionary
        self.command_handlers = {
            'tia_or_gatan': self._handle_tia_or_gatan,
            'set_gatan': self._handle_set_gatan,
            'set_tia': self._handle_set_tia,
            'acquire_4dcamera_scan': self._handle_acquire_4dcamera_scan,
            'acquire_stem_scan': self._handle_acquire_stem_scan,
            'set_roi': self._handle_set_roi,
            'move_beam': self._handle_move_beam,
            'get_pixel_size': self._handle_get_pixel_size,
        }

        # Store params for handler methods
        self.params = None

        while True:
            try:
                data = self.serverSocket.recv()
                command, self.params = pickle.loads(data)

                self.logger.info('Received command: {}'.format(command))
                self.logger.debug('Command params: {}'.format(self.params))

                # Use command dispatch dictionary
                handler = self.command_handlers.get(command)
                if handler:
                    try:
                        reply_message, reply_data = handler()
                        error = None
                        self.logger.info('Command {} completed successfully'.format(command))
                    except Exception as e:
                        # Log the full error with traceback
                        self.logger.error('Error executing command {}: {}'.format(command, str(e)))
                        self.logger.error(traceback.format_exc())
                        # Return error to client
                        reply_message = 'error executing {}'.format(command)
                        reply_data = None
                        error = str(e)
                else:
                    self.logger.warning('Unknown command received: {}'.format(command))
                    reply_message = 'unknown call'
                    reply_data = None
                    error = 'Unknown command: {}'.format(command)

                reply_d = {'reply_message': reply_message,
                           'reply_data': reply_data,
                           'error': error}

                self.serverSocket.send(pickle.dumps(reply_d))
                self.logger.debug("Idle")

            except KeyboardInterrupt:
                self.logger.info('Server shutting down due to keyboard interrupt')
                break
            except Exception as e:
                # Catch any other unexpected errors to prevent server crash
                self.logger.critical('Unexpected error in main loop: {}'.format(str(e)))
                self.logger.critical(traceback.format_exc())
                # Try to send error response to client
                try:
                    reply_d = {'reply_message': 'server error',
                               'reply_data': None,
                               'error': str(e)}
                    self.serverSocket.send(pickle.dumps(reply_d))
                except:
                    self.logger.critical('Failed to send error response to client')
                    pass

    # Command handler methods
    def _handle_tia_or_gatan(self):
        """Handle query for current mode (TIA or Gatan)"""
        return 'is_gatan', self.is_gatan

    def _handle_set_gatan(self):
        """Handle switch to Gatan mode"""
        self.is_gatan = self.set_is_gatan(True)
        return 'is_gatan', self.is_gatan

    def _handle_set_tia(self):
        """Handle switch to TIA mode"""
        self.is_gatan = self.set_is_gatan(False)
        return 'is_gatan', self.is_gatan

    def _handle_acquire_4dcamera_scan(self):
        """Handle 4D Camera scan acquisition"""
        prev_is_gatan = self.is_gatan
        if not self.is_gatan:
            self.is_gatan = self.set_is_gatan(True)
        ret = self.acquire_4dcamera_scan(self.params)
        if self.is_gatan != prev_is_gatan:
            self.is_gatan = self.set_is_gatan(prev_is_gatan)
        return 'gatan_data', ret

    def _handle_acquire_stem_scan(self):
        """Handle HAADF-STEM scan acquisition"""
        prev_is_gatan = self.is_gatan
        if not self.is_gatan:
            self.is_gatan = self.set_is_gatan(True)
        ret = self.acquire_stem_scan(self.params)
        if self.is_gatan != prev_is_gatan:
            self.is_gatan = self.set_is_gatan(prev_is_gatan)
        return 'gatan_data', ret

    def _handle_set_roi(self):
        """Handle set region of interest"""
        roi = self.params
        return 'set_roi', roi

    def _handle_move_beam(self):
        """Handle beam movement"""
        self.move_beam(self.params[0], self.params[1])
        return 'beam moved', 0

    def _handle_get_pixel_size(self):
        """Handle get pixel size from file"""
        ps = self.get_pixel_size(self.params)
        return 'pixelSize', ps
    
    def get_pixel_size(self, nn):
        """Reads the file on disk to get the pixel size

        Parameters
        ----------
        nn : int or str
            The scan number or identifier for the file

        Returns
        -------
        : float
            The pixel size (calX) from the dm file
        """
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
        self.logger.info('Writing move beam script')
        with open(self.MBSCRIPT, 'w') as f:
            f.write(mbs)
        if not self.SIM:
            # call script
            self.logger.info('Calling move beam script')
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
        self.logger.info("HAADF data shape = {}".format(data.shape))
        return data, metadata

    def call_stem_script(self, params):
        """ Acquires a STEM datset"""
        try:
            dms = dm_scripts.acquire_stem_script(dwell_time=params['dwell_time'],
                                                pwidth=params['pwidth'], pheight=params['pheight'],
                                                rotation=params['rotation'], signal_index=params['signal_index'])
            self.logger.info('Writing DM script for HAADF scan')
            with open(self.DMSCRIPT, 'w') as f:
                f.write(dms)

            # call script
            self.logger.info('Calling DM script for HAADF scan')
            with open('NUL', 'w') as _:
                call(f'\"C:\\Program Files\\Gatan\\DigitalMicrograph.exe\" /ef \"{self.DMSCRIPT}\"')
            self.logger.info('HAADF scan finished')
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
            dms = dm_scripts.acquire_4Dcamera_script(pwidth=params['pwidth'], pheight=params['pheight'],
                                                     rotation=params['rotation'], nread=params['nread'])
            self.logger.info('Writing DM script for 4D Camera scan')
            with open(self.DMSCRIPT, 'w') as f:
                f.write(dms)

            # call script
            self.logger.info('Calling DM script for 4D Camera scan')
            with open('NUL', 'w') as _:
                call(f'\"C:\\Program Files\\Gatan\\DigitalMicrograph.exe\" /ef \"{self.DMSCRIPT}\"')
            self.logger.info('4D Camera scan finished')
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
        """Send a command to the button pusher and log the response"""
        self.logger.debug("Sending to button pusher: {}".format(command))
        soc.send_string(json.dumps(command))
        response = json.loads(soc.recv_string())
        self.logger.debug("Button pusher response: {}".format(response))
        return response
    
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', action='store', type=int, default=13579, help='server port')
    parser.add_argument('--sim', action='store_true', default=False, help='simulation mode')

    args = parser.parse_args()

    port = args.port
    sim = args.sim

    server = GatanServer(sim=sim, port=port)
