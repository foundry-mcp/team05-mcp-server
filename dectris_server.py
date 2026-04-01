# -*- coding: utf-8 -*-
"""
A zmq server that communicates with the Dectris camera
and TVIPS scan controller.
"""

from pathlib import Path
import pickle
import zmq
import logging
import traceback
import argparse
import time


import winreg
from dcu_client import DEigerClient

class DectrisServer():
    def __init__(self, port=13580):
        """A server that accepts commands to control Dectris and
        TVIPS scan controller.

        Parameters
        ----------
        port : int
            The port to open for the server. The server will bind that port
            on all available interfaces.
        """
        # Camera connection parameters
        self.dcu_ip = "10.42.41.10"
        self.dcu_port = 80
        self.n_scans = 5

        # Setup logging
        self.logger = logging.getLogger('DectrisServer')
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
        file_handler = logging.FileHandler('dectris_server.log')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

        self.logger.info('Initializing DectrisServer')

        # Create server
        context = zmq.Context()
        self.serverSocket = context.socket(zmq.REP)
        self.serverSocket.bind('tcp://*:'+str(port))
        self.logger.info('Server Online on port {}'.format(port))

        # Command dispatch dictionary
        self.command_handlers = {
            'acquire_scan': self._handle_acquire_scan,
            'setup_detector': self._handle_setup_detector,
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

    def _handle_acquire_scan(self):
        """Handle Arina TVIPS scan acquisition"""

        ret = self.acquire_scan(self.params)

        return 'dectris_data', ret

    def _handle_setup_detector(self):
        """Handle Dectris detector setup"""
        ret = self.setup_detector(self.params)
        return 'dectris_setup', ret

    def acquire_scan(self, params):
        """Acquires a Arina 4D-STEM dataset using the TVIPS scan controller.
        
        Parameters
        ----------
        params : dict
            The parameter dictionary for acquiring a 4D-STEM dataset using
            an Arina camera with the TVIPS scan controller.
            It requires keys: dwell_time, width, height

        Returns
        -------
        : tuple
            A tuple containing the STEM data as a numpy array and metadata as a tuple.
        """
        self.logger.info(f"\n=== Scan {scan_index + 1} / {n_scans} ===")

        # Arm detector
        seq_id = client.sendDetectorCommand('arm')['sequence id']
        self.logger.info(f"  Armed. Sequence id: {seq_id}")

        # Start scan
        winreg.SetValueEx(reg_key, "Start", 0, winreg.REG_DWORD, 1)
        self.logger.info("  Scan started.")

        winreg.CloseKey(reg_key)
    
    def setup_detector(self, params):
        """Setup the Dectris detector with the provided parameters.

        Parameters
        ----------
        params : dict
            The parameter dictionary for setting up the Dectris detector.
            It requires keys: 

        Returns
        -------
        : str
            A message indicating the result of the setup operation.
        """
        client = DEigerClient(self.dcu_ip, self.dcu_port)

        # Configure stream and filewriter (once)
        
        self.logger.info("Configuring stream and filewriter ...")
        client.setStreamConfig('mode', 'enabled')
        client.setStreamConfig('format', 'cbor')
        client.setStreamConfig('header_detail', 'all')
        client.setMonitorConfig('mode', 'disabled')
        client.setFileWriterConfig('mode', 'enabled')
        client.setFileWriterConfig('name_pattern', 'scan_$id')
        client.setFileWriterConfig('nimages_per_file', 100000000)

        self.logger.info(f"  trigger_mode = {client.detectorConfig('trigger_mode')['value']}")
        self.logger.info(f"  nimages      = {client.detectorConfig('nimages')['value']}")
        self.logger.info(f"  ntrigger     = {client.detectorConfig('ntrigger')['value']}")
        self.logger.info(f"  count_time   = {client.detectorConfig('count_time')['value']} s")
        self.logger.info(f"  frame_time   = {client.detectorConfig('frame_time')['value']} s")

        # Open registry key once, keep it open for all scans
        reg_key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\TVIPS_GMBH\ScanGen",
            0,
            winreg.KEY_ALL_ACCESS,
        )
        
        self.logger.info("Setting up Dectris detector with params: {}".format(params))
        
        # Simulate some setup time
        time.sleep(1)
        
        return "Dectris detector setup complete with parameters: {}".format(params)
    
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', action='store', type=int, default=13580, help='server port')

    args = parser.parse_args()

    port = args.port

    server = DectrisServer(port=port)
