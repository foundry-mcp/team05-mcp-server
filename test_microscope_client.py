#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test client for microscope_server.py

This script connects to the microscope server and tests each command
to verify that the refactored code works correctly on the actual microscope.

Usage:
    python test_microscope_client.py --host localhost --port 7001

@author: Test script for TEAM 0.5 microscope server
"""

import zmq
import pickle
import argparse
import time
from datetime import datetime


class MicroscopeTestClient():
    def __init__(self, host='localhost', port=7001):
        """Initialize connection to microscope server"""
        self.host = host
        self.port = port

        # Setup ZMQ connection
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect(f'tcp://{host}:{port}')

        print(f"Connected to microscope server at {host}:{port}")
        print("="*60)

        # Test results tracking
        self.passed = 0
        self.failed = 0
        self.errors = []

    def send_command(self, command_dict):
        """Send command to server and return response"""
        try:
            self.socket.send(pickle.dumps(command_dict))
            response = self.socket.recv()
            return pickle.loads(response)
        except Exception as e:
            print(f"ERROR: Communication failure: {str(e)}")
            return None

    def test_command(self, name, command_dict, expect_data=None):
        """Test a single command and report results"""
        print(f"\nTesting: {name}")
        print(f"  Command: {command_dict['type']}")

        start_time = time.time()
        response = self.send_command(command_dict)
        elapsed = time.time() - start_time

        if response is None:
            print(f"  ❌ FAILED - No response")
            self.failed += 1
            self.errors.append(name)
            return False

        # Check for errors
        if response.get('error'):
            print(f"  ❌ FAILED - Error: {response['error']}")
            print(f"  Message: {response['reply_message']}")
            self.failed += 1
            self.errors.append(name)
            return False

        # Success
        print(f"  ✓ PASSED ({elapsed:.3f}s)")
        print(f"  Message: {response['reply_message']}")
        if response['reply_data'] is not None and expect_data:
            print(f"  Data: {response['reply_data']}")

        self.passed += 1
        return True

    def run_all_tests(self):
        """Run all test commands"""
        print("\nStarting Microscope Server Tests")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)

        # 1. Test ping (basic connectivity)
        print("\n" + "="*60)
        print("BASIC CONNECTIVITY TESTS")
        print("="*60)
        self.test_command(
            "Ping",
            {'type': 'ping'}
        )

        # 2. Test getter commands (safe, read-only)
        print("\n" + "="*60)
        print("GETTER COMMANDS (Read-Only)")
        print("="*60)

        self.test_command(
            "Get Voltage",
            {'type': 'get_voltage'},
            expect_data=True
        )

        self.test_command(
            "Get Magnification",
            {'type': 'get_mag'},
            expect_data=True
        )

        self.test_command(
            "Get Stage Position",
            {'type': 'get_stage_pos'},
            expect_data=True
        )

        self.test_command(
            "Get Defocus",
            {'type': 'get_defocus'},
            expect_data=True
        )

        self.test_command(
            "Get Camera Length",
            {'type': 'get_camera_length'},
            expect_data=True
        )

        self.test_command(
            "Get Camera Length Index",
            {'type': 'get_camera_length_index'},
            expect_data=True
        )

        self.test_command(
            "Get STEM Rotation",
            {'type': 'get_stem_rotation'},
            expect_data=True
        )

        self.test_command(
            "Get Convergence Angle",
            {'type': 'get_convergence_angle'},
            expect_data=True
        )

        self.test_command(
            "Get Condenser Stigmator",
            {'type': 'get_condenser_stigmator'},
            expect_data=True
        )

        # 3. Test beam control
        print("\n" + "="*60)
        print("BEAM CONTROL TESTS")
        print("="*60)

        self.test_command(
            "Blank Beam",
            {'type': 'blank_beam'}
        )

        time.sleep(0.5)

        self.test_command(
            "Unblank Beam",
            {'type': 'unblank_beam'}
        )

        # 4. Test screenshot
        print("\n" + "="*60)
        print("SCREENSHOT TEST")
        print("="*60)

        self.test_command(
            "Get Screenshot",
            {'type': 'get_screenshot'}
        )

        # 5. Test stage movement (very small, safe movement)
        print("\n" + "="*60)
        print("STAGE MOVEMENT TESTS (Small Delta)")
        print("="*60)

        print("\nWARNING: About to test small stage movement")
        print("This will move the stage by 1 nanometer in X")
        response = input("Continue? (yes/no): ")

        if response.lower() == 'yes':
            self.test_command(
                "Move Stage Delta (1nm in X)",
                {
                    'type': 'move_stage',
                    'dX': 1e-9,  # 1 nanometer
                    'dY': 0,
                    'dZ': 0,
                    'dA': 0,
                    'dB': 0
                }
            )

            time.sleep(1)

            # Move back
            self.test_command(
                "Move Stage Delta (return)",
                {
                    'type': 'move_stage',
                    'dX': -1e-9,  # move back
                    'dY': 0,
                    'dZ': 0,
                    'dA': 0,
                    'dB': 0
                }
            )
        else:
            print("  Skipped stage movement tests")

        # 6. Test image acquisition (WARNING: This unblanks beam)
        print("\n" + "="*60)
        print("IMAGE ACQUISITION TEST")
        print("="*60)

        print("\nWARNING: This will acquire a small test image")
        print("Image parameters: 64x64 pixels, 1e-6 second dwell time")
        response = input("Continue? (yes/no): ")

        if response.lower() == 'yes':
            self.test_command(
                "Acquire Small Test Image",
                {
                    'type': 'image',
                    'dwell': 1e-6,  # 1 microsecond
                    'shape': (64, 64),  # small image
                    'offset': (0, 0)
                }
            )
        else:
            print("  Skipped image acquisition test")

        # 7. Test unknown command (should handle gracefully)
        print("\n" + "="*60)
        print("ERROR HANDLING TEST")
        print("="*60)

        print("\nTesting unknown command (should fail gracefully):")
        response = self.send_command({'type': 'invalid_command_xyz'})
        if response and response.get('error'):
            print("  ✓ PASSED - Unknown command handled correctly")
            print(f"  Message: {response['reply_message']}")
            print(f"  Error: {response['error']}")
            self.passed += 1
        else:
            print("  ❌ FAILED - Unknown command not handled properly")
            self.failed += 1

        # Print summary
        self.print_summary()

    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        print(f"Total Passed: {self.passed}")
        print(f"Total Failed: {self.failed}")
        print(f"Success Rate: {self.passed/(self.passed+self.failed)*100:.1f}%")

        if self.errors:
            print("\nFailed tests:")
            for error in self.errors:
                print(f"  - {error}")
        else:
            print("\n🎉 All tests passed!")

        print("="*60)

    def cleanup(self):
        """Close connection"""
        self.socket.close()
        self.context.term()
        print("\nConnection closed")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Test microscope server commands')
    parser.add_argument('--host', type=str, default='localhost',
                       help='Server hostname (default: localhost)')
    parser.add_argument('--port', type=int, default=7001,
                       help='Server port (default: 7001)')

    args = parser.parse_args()

    # Create test client and run tests
    client = MicroscopeTestClient(host=args.host, port=args.port)

    try:
        client.run_all_tests()
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
    except Exception as e:
        print(f"\n\nUnexpected error: {str(e)}")
    finally:
        client.cleanup()
