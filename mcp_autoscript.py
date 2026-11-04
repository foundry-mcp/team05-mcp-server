# -*- coding: utf-8 -*-
"""
Created on Thu Aug 21 14:00:45 2025

This is a set of MCP commands for the TEAM 0.5 microscope using the
Thermo Fisher AutoScript TEM API. Unlike mcp_library.py, this file
connects directly to the microscope via AutoScript instead of going
through a separate ZeroMQ microscope_server.py process running
TEMScripting/TIA COM calls.

This file covers core microscope functionality only. BEACON (CEOS
aberration correction, autofocus) and the Gatan/DigitalMicrograph
server integration are not included.

@author: Peter Ercius, Alex Pattison, Morgan Wall, Stephanie Ribet
"""

from pathlib import Path
import argparse
from typing import Optional

import numpy as np
import numpy.typing as npt

from fastmcp import FastMCP

from fastmcp.resources import FileResource

import h5py
import mfid

from autoscript_tem_microscope_client import TemMicroscopeClient
from autoscript_tem_microscope_client.enumerations import *
from autoscript_tem_microscope_client.structures import *

mcp = FastMCP("TEAM05_Controller")

parameters_path = Path(__file__).with_name("TEAM0.5_Parameters.md").resolve()

mcp.add_resource(
    FileResource(
        name="TEAM0.5_Parameters",
        uri=parameters_path.as_uri(),
        path=parameters_path,
        mime_type="text/markdown",
        description=(
        "Reference calibration tables and hardware parameters for the TEAM 0.5 TEM/STEM instrument across operating voltages (50 kV, 80 kV, 200 kV, 300 kV). "
        "READ THIS FILE WHEN: "
        "1. Calculating frame times and selecting optimal STEM dwell/flyback times to prevent timing artifacts. "
        "2. Matching HAADF-STEM camera lengths (mm) to target inner/outer collection semi-angles (mrad). "
        "3. Configuring 4D-STEM acquisitions, including camera length calibrations (camera constant, pixel size in Å⁻¹) and differential phase contrast (DPC) rotation/flip offsets (-160° for 80 kV, -9° for 200/300 kV). "
        "4. Checking spatial sampling limits via OneView camera Nyquist frequencies across magnifications. "
        "CONTAINS: Standard operating presets, collection semi-angle lookup tables, camera constant calibrations, DPC offset angles, and beam current picoammeter reference notes."
    ),
    )
)


def _nearest_label(target, available_values):
    '''
    AutoScript magnification and camera length are only settable to
    discrete labelled steps (unlike TEMScripting's free float value or
    instrument-defined index). This picks the closest available step
    to a requested target value.

    Parameters
    ----------
    target : float
        Desired value (e.g. magnification or camera length in meters).
    available_values : list
        List of objects with a `.nominal` and `.label` attribute, as
        returned by `optics.magnification.available_values` or
        `optics.camera_length.available_values`.

    Returns
    -------
    : the element of available_values with `.nominal` closest to target
    '''
    return min(available_values, key=lambda v: abs(v.nominal - target))


def create_dims(dataTop, pix):
    """ Create dims for the EMD file."""

    dim2 = dataTop.create_dataset('dim2', (pix[1],), 'f')
    dim2.attrs['name'] = 'X'
    dim2.attrs['units'] = 'n_m'
    dim1 = dataTop.create_dataset('dim1', (pix[0],), 'f')
    dim1.attrs['name'] = 'Y'
    dim1.attrs['units'] = 'n_m'

    return 1

def write_emd_data(file_path, data, calX, calY, user_name='Claude', sample_name=''):
    with h5py.File(file_path, 'w') as f:
        shape = data.shape
        md = autoscript_microscope.get_metadata()

        dataroot = f.create_group('/data')

        # Initialize the data set
        dataTop = dataroot.create_group('single')
        dset = dataTop.create_dataset('data', shape, data.dtype)

        # Create the EMD dimension datasets
        _ = create_dims(dataTop, shape)

        microscope_group = f.create_group('microscope')
        if md:
            metadata_keys = [
                'mode',
                'high tension',
                'spot size index',
                'defocus',
                'convergence angle',
                'camera length',
                'camera length index',
                'condenser stigmator',
                'diffraction shift',
                'stage position',
                'stem rotation',
                'stem field of view',
                'stem magnification',
            ]
            for key in metadata_keys:
                if key in md:
                    microscope_group.attrs[key] = md[key]

        user = f.create_group('user')
        user.attrs['user name'] = user_name

        sample = f.create_group('sample')
        sample.attrs['sample name'] = sample_name

        dims = [dataTop['dim1'], dataTop['dim2']]

        imageShape = data.shape[-2:]
        xdim = np.linspace(0, (imageShape[0]-1) * calX * 1e9, imageShape[0]) # multiply by 1e9 for nanometers
        ydim = np.linspace(0, (imageShape[1]-1) * calY * 1e9, imageShape[1])
        dims[-1][:] = ydim
        dims[-2][:] = xdim

        # Add as attribute so loading in Fiji provides pixel size
        # Note: Must be 3D so set the first element to 1
        fiji_element_size = (1, calY*1e6, calX*1e6)

        dset[:] = data

        # Create an attribute for easy loading into Fiji using HDF5 import
        dset.attrs['element_size_um'] = np.asarray(fiji_element_size).astype(np.float32)

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


class AutoScriptMicroscope():
    """Implements connectivity to the microscope via the AutoScript TEM API.

    This replaces the TEMScripting/TIA COM calls in
    microscope_server.py's MicroscopeControl class, connecting directly
    to the microscope instead of going through a separate ZeroMQ server.
    """
    def __init__(self, microscope):
        self._microscope = microscope
        self.optics = microscope.optics
        self.vacuum = microscope.vacuum
        self.specimen = microscope.specimen
        self.source = microscope.source
        self.detectors = microscope.detectors
        self.acquisition = microscope.acquisition

    def open_column_valve(self):
        """Opens the microscope column valves"""
        self.vacuum.column_valves.open()
        print('Column valves open')

    def close_column_valve(self):
        """Closes the microscope column valves"""
        self.vacuum.column_valves.close()
        print('Column valves closed')

    def get_mag(self):
        """Get the STEM magnification.

        Returns
        -------
        : float
        The STEM magnification value.
        """
        return self.optics.magnification.value.nominal

    def set_mag(self, mag):
        """Set the STEM magnification to the closest available labelled step.

        Parameters
        ----------
        mag : float
            The desired magnification as a number. e.x. 1.8 Mx is 1800000
        """
        self.optics.projector_mode = ProjectorMode.IMAGING
        available = self.optics.magnification.available_values
        nearest = _nearest_label(mag, available)
        self.optics.set_projector(nearest.label)
        print('Mag set to {}'.format(self.optics.magnification.value.nominal))

    def get_stem_rotation(self):
        """Get the STEM rotation in radians.

        Returns
        -------
        : float
        The STEM rotation value in radians.
        """
        return self.optics.scan_rotation

    def set_stem_rotation(self, rot):
        """Set the STEM rotation in radians.

        Parameters
        ----------
        rot : float
            The rotation in radians.
        """
        self.optics.scan_rotation = rot
        print('STEM rotation set to {}'.format(self.optics.scan_rotation))

    def get_stem_convergence_angle(self):
        """Get the STEM convergence angle in radians.

        Returns
        -------
        : float
        The STEM convergence angle in radians.
        """
        return self.optics.convergence_angle

    def get_stage_pos(self):
        ''' Get the stage position. This returns the X, Y, Z position (meters)
        and the alpha and beta tilt angles (radians).

        Returns
        -------
        : tuple (float, float, float, float, float)
           The X, Y, Z, alpha, beta values of the stage. The position
           is in meters and the angles are in radians. Beta is 0.0 if
           the current holder does not support beta tilt.
        '''
        pos = self.specimen.stage.position
        beta = pos.b if pos.b is not None else 0.0
        return pos.x, pos.y, pos.z, pos.a, beta

    def get_holder_type(self):
        """Returns the holder type.

        A single tilt holder can only tilt the sample using the alpha value. The double tilt
        holder can tilt along two orthogonal axes called alpha and beta.

        Returns
        -------
        : HolderType
        The AutoScript HolderType enum value (e.g. SINGLE_TILT, DOUBLE_TILT, NONE).
        """
        holder = self.specimen.stage.get_holder_type()
        print('holder = {}'.format(holder))
        return holder

    def move_stage_delta(self, dX=0, dY=0, dZ=0, dA=0, dB=0):
        ''' Move stage by delta value. This changes the stage position by the requested
        values rather than to an absolute position. The position values are in meters and the
        angle values are in radians.

        Parameters
        ----------
        dX, dY, dZ : float
        The change in stage position values in meters
        dA, dB : float
        The change in stage alpha and beta rotation values in radians. dB is ignored
        if the current holder does not support beta tilt.

        Returns
        -------
        : 0 or None
        Returns 0 if there is an error. Otherwise returns None
        '''
        holder = self.get_holder_type()
        if holder == HolderType.SINGLE_TILT:
            delta = StagePosition(x=float(dX), y=float(dY), z=float(dZ), a=float(dA))
        elif holder == HolderType.DOUBLE_TILT:
            delta = StagePosition(x=float(dX), y=float(dY), z=float(dZ), a=float(dA), b=float(dB))
        else:
            print('Can not move holder named {}'.format(holder))
            return 0

        self.specimen.stage.relative_move_safe(delta)

    def move_stage_goto(self, X, Y, Z, A, B):
        """Set the stage position to the values indicated. This moves directly
        to those coordinates. X, Y, Z are in meters and alpha, beta are in
        radians. Beta tilt is only applied if a double tilt holder is detected.

        None values will not be used and the stage position of that axis will be
        kept the same.

        Parameters
        ----------
        X, Y, Z : float | None
        The stage position values in meters
        A, B : float | None
        The stage alpha and beta rotation values in radians.

        Returns
        -------
        : 0 or None
        Returns 0 if there is an error. Otherwise returns None
        """
        holder = self.get_holder_type()
        if holder not in (HolderType.SINGLE_TILT, HolderType.DOUBLE_TILT):
            print('Can not move holder named {}'.format(holder))
            return 0

        if holder == HolderType.SINGLE_TILT:
            B = None

        print('Going to {}, {}, {}, {}, {}'.format(X, Y, Z, A, B))
        target = StagePosition(x=X, y=Y, z=Z, a=A, b=B)
        self.specimen.stage.absolute_move_safe(target)

    def blank(self):
        ''' Blanks beam '''
        self.optics.blanker.blank()
        print('Beam blanked')

    def unblank(self):
        ''' Unblanks beam '''
        self.optics.blanker.unblank()
        print('Beam unblanked')

    def get_voltage(self):
        ''' Returns the gun accelerating voltage in volts.

        Returns
        -------
        : float
        The accelerating voltage. The high tension in V
        '''
        return self.source.acceleration_voltage.value

    def get_condenser_stigmator(self):
        """Returns the current value of the condenser stigmator in meters.

        Returns
        -------
        : tuple (float, float)
        The microscope condenser stigmator as a 2-tuple with (A1_x, A1_y) in meters.
        """
        stig = self.optics.stigmators.condenser_stigmator
        return (stig.x, stig.y)

    def set_condenser_stigmator(self, stig):
        """Sets the current value of the condenser stigmator in meters.

        Parameters
        ----------
        stig : tuple (float, float)
        The desired microscope condenser stigmator as a 2-tuple with (A1_x, A1_y) in meters.
        """
        self.optics.stigmators.condenser_stigmator = Point(stig[0], stig[1])

    def get_stem_intensity_defocus(self):
        ''' Returns the STEM "intensity" (condenser) defocus component in meters.

        Returns
        -------
        : float
        '''
        return self.optics.focusing.stem.intensity.defocus

    def set_stem_intensity_defocus(self, target_df):
        '''
        Sets the STEM "intensity" (condenser) defocus component to a specific value.

        Parameters
        ----------
        target_df : float
            Target defocus (in meters)
        '''
        self.optics.focusing.stem.intensity.defocus = target_df
        print('Intensity defocus set to {}'.format(self.optics.focusing.stem.intensity.defocus))

    def get_stem_objective_defocus(self):
        ''' Returns the STEM objective lens defocus component in meters.

        Returns
        -------
        : float
        '''
        return self.optics.focusing.stem.objective.defocus

    def set_stem_objective_defocus(self, target_df):
        '''
        Sets the STEM objective lens defocus component to a specific value.

        Parameters
        ----------
        target_df : float
            Target defocus (in meters)
        '''
        self.optics.focusing.stem.objective.defocus = target_df
        print('Objective defocus set to {}'.format(self.optics.focusing.stem.objective.defocus))

    def microscope_acquire_image(self, dwell, shape, offset=(0, 0)):
        '''
        Acquire a STEM image using the AutoScript HAADF detector.

        Parameters
        ----------
        dwell : float
            Dwell time in seconds
        shape : tuple, array
            Image shape (width, height) in pixels
        offset : tuple, array
            Pixel offset of the scanned region's top-left corner.

        Returns
        -------
        image_data, calX, calY, unitName
            Acquired image as a numpy array, the x and y pixel
            calibration, and the calibration unit name.
        '''
        sizeX = int(shape[0])
        sizeY = int(shape[1])
        offsetX = int(offset[0])
        offsetY = int(offset[1])

        print('Acquiring image with shape = {}, {}, offset = {}, {}'.format(sizeX, sizeY, offsetX, offsetY))

        # StemAcquisitionSettings.size is a single int (square full-frame scan
        # resolution), not a (width, height) tuple. A non-square or offset
        # image is cropped out of that square scan via `region` instead.
        full_size = max(sizeX, sizeY)
        settings = StemAcquisitionSettings(
            dwell,
            detector_types=[DetectorType.HAADF],
            size=full_size,
            region=Region(RegionCoordinateSystem.PIXELS, rectangle=(offsetX, offsetY, sizeX, sizeY)),
        )

        self.unblank()
        try:
            images = self.acquisition.acquire_stem_images_advanced(settings)
        finally:
            # Always re-blank, even if the acquisition call raises, so a
            # failed acquisition doesn't leave the beam unblanked or the
            # detector marked busy for the next acquisition call.
            self.blank()

        image = images[0]
        image_data = np.array(image.data)
        calX = image.metadata.binary_result.pixel_size.x
        calY = image.metadata.binary_result.pixel_size.y
        unitName = str(image.metadata.binary_result.pixel_size_x_unit)

        return image_data, calX, calY, unitName

    def microscope_acquire_flucam_image(self, exposure_time, size):
        '''
        Acquire an image using the FluCam (fluorescent screen camera).

        The FluCam shares the main fluorescent screen with the HAADF
        detector path; the acquisition call inserts the screen/detector
        automatically, no manual insert/retract is needed. FluCam
        images are not a calibrated real-space detector, so pixel
        size/units may not be meaningful or populated.

        Parameters
        ----------
        exposure_time : float
            Exposure time in seconds.
        size : int
            Square image size in pixels.

        Returns
        -------
        image_data, calX, calY, unitName
            Acquired image as a numpy array, the x and y pixel
            calibration, and the calibration unit name. calX/calY/unitName
            fall back to (1, 1, 'pixel') if no calibration is available.
        '''
        print('Acquiring FluCam image with size = {}, exposure = {}'.format(size, exposure_time))

        image = self.acquisition.acquire_camera_image(CameraType.FLUCAM, int(size), exposure_time)
        image_data = np.array(image.data)

        try:
            calX = image.metadata.binary_result.pixel_size.x
            calY = image.metadata.binary_result.pixel_size.y
            unitName = str(image.metadata.binary_result.pixel_size_x_unit)
        except Exception:
            calX, calY, unitName = 1, 1, 'pixel'

        return image_data, calX, calY, unitName

    def get_camera_length(self):
        return self.optics.camera_length.value.nominal

    def get_camera_length_index(self):
        """Returns the index of the current camera length within the list
        of available camera length steps. Unlike TEMScripting's
        CameraLengthIndex this is not an instrument-defined index, but a
        position within `optics.camera_length.available_values`.
        """
        available = self.optics.camera_length.available_values
        current = self.optics.camera_length.value.nominal
        nearest = _nearest_label(current, available)
        return available.index(nearest)

    def set_camera_length_index(self, CL_index):
        """Sets the camera length by index into the list of available
        camera length steps (see get_camera_length_index)."""
        self.optics.projector_mode = ProjectorMode.DIFFRACTION
        available = self.optics.camera_length.available_values
        self.optics.set_projector(available[CL_index].label)
        print('Camera length set to {}'.format(self.optics.camera_length.value.nominal))

    def get_screen_current(self):
        return self.detectors.screen.measure_current()

    def get_screen_position(self):
        return self.detectors.screen.position

    def set_screen_position(self, screen_position:int):
        """Set the screen position. 2=up (retracted), 3=down (inserted),
        matching the TEMScripting convention used by mcp_library.py."""
        if type(screen_position) is not int:
            raise TypeError('screen_position must be an integer')
        if screen_position not in (2, 3):
            raise ValueError('screen_position must be 2 (up) or 3 (down)')
        if screen_position == 2:
            self.detectors.screen.retract()
        else:
            self.detectors.screen.insert()

    def get_metadata(self):
        """ Gets some useful parameters about the microscope's
        current settings. """
        md = {}
        md['microscope name'] = "TEAM 0.5"
        md['mode'] = self._create_mode_string()
        md['high tension'] = self.get_voltage()
        md['spot size index'] = self.optics.spot_size_index
        md['defocus'] = self.get_stem_intensity_defocus() + self.get_stem_objective_defocus()
        md['convergence angle'] = self.get_stem_convergence_angle()
        md['camera length'] = self.get_camera_length()
        md['camera length index'] = self.get_camera_length_index()
        md['condenser stigmator'] = self.get_condenser_stigmator()
        md['diffraction shift'] = self.get_diffraction_shift()
        md['stage position'] = self.get_stage_pos()
        try:
            md['stem rotation'] = self.get_stem_rotation()
            md['stem magnification'] = self.get_mag()
        except Exception:
            pass
        return md

    def _create_mode_string(self):
        """Build a mode string. This has information about the
        scanning mode: STEM or TEM
        illumination mode: microprobe or nanoprobe
        projection mode: image or diffraction
        projection submode: only SA is currently supported

        NOTE: SA sub-mode detection is best-effort and has not been
        verified against real AutoScript hardware.
        """
        mode = ''
        if self.optics.optical_mode == OpticalMode.STEM:
            mode += 'STEM'
        elif self.optics.optical_mode == OpticalMode.TEM:
            mode += 'TEM'

        if self.optics.probe_mode == ProbeMode.NANO_PROBE:
            mode += ' nanoprobe'
        elif self.optics.probe_mode == ProbeMode.MICRO_PROBE:
            mode += ' microprobe'

        if self.optics.projector_mode == ProjectorMode.DIFFRACTION:
            mode += ' diffraction'
        elif self.optics.projector_mode == ProjectorMode.IMAGING:
            mode += ' image'

        print('mode = {}'.format(mode))
        return mode

    def get_beam_tilt(self):
        """Get the STEM beam tilt in radians.

        Returns
        -------
        : tuple (float, float)
        The STEM beam tilt value in radians.
        """
        tilt = self.optics.deflectors.beam_tilt
        return (tilt.x, tilt.y)

    def set_beam_tilt(self, beam_tilt, diff_shift=None):
        """  Sets the beam tilt using optics.deflectors.beam_tilt. The
        diff_shift keyword can be used to compensate for shift of the
        beam on the detector using the diffraction shift equivalent
        (image_tilt). Ideally, the diff_shift and beam tilt should be
        the same value but miscalibration might make it necessary to
        change those values.

        Parameters
        ----------
        beam_tilt : tuple, 2 floats
            The X and Y beam tilt in units of radians. The maximum
            beam tilt is about .200 radians
        diff_shift : tuple, 2 floats
            The X and Y diffraction shift (image tilt) to apply to
            compensate for beam motion on the detector. The shift is
            in radians and should be the negative of the beam tilt.
        """
        if not diff_shift:
            diff_shift = (0, 0)

        self.optics.deflectors.beam_tilt = Point(beam_tilt[0], beam_tilt[1])
        self.set_diffraction_shift(diff_shift)

    def get_diffraction_shift(self):
        """Get the STEM diffraction shift in radians.

        NOTE: AutoScript has no dedicated diffraction shift deflector.
        This is implemented using optics.deflectors.image_tilt as a
        stand-in and has not been verified against real hardware.

        Returns
        -------
        : tuple of floats
            The STEM diffraction X and Y shift values in radians.
        """
        shift = self.optics.deflectors.image_tilt
        return (shift.x, shift.y)

    def set_diffraction_shift(self, diff_shift):
        """  Sets the diffraction shift in radians.

        NOTE: AutoScript has no dedicated diffraction shift deflector.
        This is implemented using optics.deflectors.image_tilt as a
        stand-in and has not been verified against real hardware.

        Parameters
        ----------
        diff_shift : tuple of floats
            The X and Y diffraction shift values in radians.
        """
        self.optics.deflectors.image_tilt = Point(diff_shift[0], diff_shift[1])


###
# MCP tools - microscope commands
###

@mcp.tool()
def acquire_image(dwell:float=2e-6, shape:tuple=(256,256)):
    '''
    Acquire HAADF-STEM image. A tuple is returned with information
    about the image. The image is saved to disk as a Berkeley
    EMD file at the file path returned from this function.

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
    image, calx, caly, cal_unit_name = autoscript_microscope.microscope_acquire_image(dwell, shape, offset)
    image_min = image.min()
    image_max = image.max()
    image_std = image.std()

    new_id = mfid.mfid()
    dir_path = Path('D:/user_data/Claude')
    file_path = dir_path / Path(f'{new_id[0]}.emd')
    write_emd_data(str(file_path), image, calx, caly, user_name='Claude', sample_name='')

    return (str(file_path), calx, caly, cal_unit_name, image_min, image_max, image_std)

@mcp.tool()
def acquire_flucam_image(exposure_time:float=0.1, size:int=1024):
    '''
    Acquire an image using the FluCam (fluorescent screen camera). A
    tuple is returned with information about the image. The image is
    saved to disk as a Berkeley EMD file at the file path returned
    from this function.

    The FluCam is not a calibrated real-space detector like the
    HAADF-STEM detector, so the pixel calibration and units may not
    be meaningful; they fall back to (1, 1, 'pixel') if unavailable.

    Parameters
    ----------
    exposure_time : float
        Exposure time in seconds. The default is 0.1 seconds.
    size : int
        Square image size in pixels. The default is 1024.

    Returns
    -------
    : tuple (str, float, float, string, float, float, float)
        The tuple is made of 7 elements. The description of the elements are
        file path, (x pixel calibration, y pixel calibration, the calibration unit name,
        the image minimum, the image maximum, and the image standard deviation).
    '''

    image, calx, caly, cal_unit_name = autoscript_microscope.microscope_acquire_flucam_image(exposure_time, size)
    image_min = image.min()
    image_max = image.max()
    image_std = image.std()

    new_id = mfid.mfid()
    dir_path = Path('D:/user_data/Claude')
    file_path = dir_path / Path(f'{new_id[0]}.emd')
    write_emd_data(str(file_path), image, calx, caly, user_name='Claude', sample_name='')

    return (str(file_path), calx, caly, cal_unit_name, image_min, image_max, image_std)

@mcp.tool()
def get_mag():
    '''
    Get current STEM magnification as an integer.

    Returns
    -------
    : int
        Current magnification.

    '''
    return autoscript_microscope.get_mag()

@mcp.tool()
def set_mag(mag:int):
    '''
    Set the STEM magnification to the closest available labelled step.

    Parameters
    ----------
    mag : int
        Magnification value.

    Returns
    -------
    None

    '''
    autoscript_microscope.set_mag(mag)

@mcp.tool()
def get_convergence_angle():
    '''
    Get current STEM convergence angle in radians.

    Returns
    -------
    : float
        STEM convergence angle in radians.

    '''
    return autoscript_microscope.get_stem_convergence_angle()

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
    return autoscript_microscope.get_stage_pos()

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
        Change in beta alngle in radians (ignored if holder does not support beta tilt). The default is 0.

    Returns
    -------
    None.

    '''
    autoscript_microscope.move_stage_delta(dX, dY, dZ, dA, dB)

@mcp.tool()
def move_stage_absolute(X:float | None, Y:float|None, Z:float|None, A:float|None, B:float|None):
    '''
    Moves and tilts stage to the desired position. The values
    of X, Y, and Z are in are in meters. A is alpha tilt and B is beta tilt. The values of A and B are angles
    which are used to tilt the stage. A is similar to roll and B is similar to pitch in an airplane. There is
    no way to implement a yaw rotation.

    If a input value is None then the current stage position is kept constant.

    Parameters
    ----------
    X : float, optional
        New x position in meters.
    Y : float, optional
        New y position in meters.
    Z : float, optional
        New z position in meters.
    A : float, optional
        New alpha angle in radians.
    B : float, optional
        New beta alngle in radians

    Returns
    -------
    None.

    '''
    autoscript_microscope.move_stage_goto(X, Y, Z, A, B)

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
    return autoscript_microscope.get_camera_length()

@mcp.tool()
def get_camera_length_index():
    '''
    Get current STEM camera length index. This is the position of the
    current camera length within the list of available camera length
    steps (not an instrument-defined index as in TEMScripting).

    Returns
    -------
    : int
        The STEM camera length index.

    '''
    return autoscript_microscope.get_camera_length_index()

@mcp.tool()
def set_camera_length_index(CL_index:int):
    '''
    Set the STEM camera length by index into the list of available
    camera length steps.

    Parameters
    ----------
    CL_index : int
        Camera length index.

    Returns
    -------
    None

    '''
    autoscript_microscope.set_camera_length_index(CL_index)

@mcp.tool()
def get_screen_current():
    '''
    Get the current measured beam current from the microscope screen in Amperes.

    If this is 0.0 then several things could be wrong:
     - The screen is up and out of the beam path
     - The beam is blanked
     - The column valve is closed
     - The beam current is too low to be measured by the screen current meter (< 0.04 nanoamperes)

    Returns
    -------
    : float
        Screen current in Amperes

    '''
    return autoscript_microscope.get_screen_current()

@mcp.tool()
def get_screen_position():
    '''
    Get the current microscope screen position. When the screen is up it is
    out of the beam path and when it is down it is in the beam path.
    The screen position is returned as a tuple with two elements. The first element is the position value
    and the second element is a string description of the position.

    Returns
    -------
    : tuple (int, str)
        The position of the main screen as a tuple. Element 0 is the position value, element 1 is the position description.

    '''
    position = autoscript_microscope.get_screen_position()
    if position == ScreenPosition.RETRACTED:
        return (2, 'Screen is up and out of the beam path')
    elif position == ScreenPosition.INSERTED:
        return (3, 'Screen is down and in the beam path')
    else:
        return (0, 'Screen is in an unknown position')

@mcp.tool()
def set_screen_position(screen_position:int):
    '''
    Set the microscope's main screen position using the TEMScripting screen value.

    The possible values are:
    2 = Raise the screen up out of the beam path
    3 = Lower the screen down into the beam path

    Parameters
    ----------
    screen_position : int
        TEMScripting screen position value: 2 raises the screen and 3 lowers it.

    '''
    autoscript_microscope.set_screen_position(screen_position)

@mcp.tool()
def set_diffraction_shift(shift:tuple):
    '''
    Set the diffraction shift in STEM mode. The shift
    is applied in radians.

    NOTE: AutoScript has no dedicated diffraction shift deflector; this
    is implemented using image_tilt as a stand-in and has not been
    verified against real hardware.

    Parameters
    ----------
    shift : tuple
        The X and Y shift values in radians

    Returns
    -------
    None

    '''
    autoscript_microscope.set_diffraction_shift(shift)

@mcp.tool()
def get_diffraction_shift():
    '''
    Get the diffraction shift in STEM mode.

    NOTE: AutoScript has no dedicated diffraction shift deflector; this
    is implemented using image_tilt as a stand-in and has not been
    verified against real hardware.

    Returns
    -------
    : tuple
    The X and Y diffraction shifts in radians.
    '''
    return autoscript_microscope.get_diffraction_shift()

@mcp.tool()
def set_beam_tilt(tilt:tuple):
    '''
    Set the beam tilt in STEM mode. The diffraction shift
    is compensated for automatically with the opposite
    shift in radians.

    Parameters
    ----------
    tilt : tuple
        The X and Y tilt values in radians

    Returns
    -------
    None

    '''
    diff_shift = (-tilt[0], -tilt[1])
    autoscript_microscope.set_beam_tilt(tilt, diff_shift=diff_shift)

@mcp.tool()
def get_beam_tilt():
    '''
    Get the beam tilt in STEM mode.

    Returns
    -------
    : tuple

    '''
    return autoscript_microscope.get_beam_tilt()

@mcp.tool()
def open_column_valve():
    '''
    Opens the column valves.

    Returns
    -------
    : str
    reply message

    '''
    autoscript_microscope.open_column_valve()
    return 'column valve open'

@mcp.tool()
def close_column_valve():
    '''
    Close the column valves.

    Returns
    -------
    : str
    reply message.

    '''
    autoscript_microscope.close_column_valve()
    return 'column valve closed'

@mcp.tool()
def blank_beam():
    '''
    Blank the beam

    Returns
    -------
    : str
        Reply message.

    '''
    autoscript_microscope.blank()
    return 'beam blanked'

@mcp.tool()
def unblank_beam():
    '''
    Unblank the beam

    Returns
    -------
    str: reply message.

    '''
    autoscript_microscope.unblank()
    return 'beam unblanked'

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
    return autoscript_microscope.get_voltage()

@mcp.tool()
def get_stem_rotation_angle():
    '''
    Get the STEM scanning rotation angle. This is returned in radians.

    Returns
    -------
    : float
        The STEM scanning rotation angle in radians

    '''
    return autoscript_microscope.get_stem_rotation()

@mcp.tool()
def set_stem_rotation_angle(rotation_angle:float=0.0):
    '''
    Set the STEM scanning rotation angle in radians.

    Returns
    -------
    : str
        A response telling you the command succeeded

    '''
    autoscript_microscope.set_stem_rotation(rotation_angle)
    return 'stem rotation set'

@mcp.tool()
def get_stem_intensity_defocus():
    '''
    Get the STEM "intensity" (condenser) defocus component of the microscope.

    Returns
    -------
    : float
        Current intensity defocus value in meters.

    '''
    return autoscript_microscope.get_stem_intensity_defocus()

@mcp.tool()
def set_stem_intensity_defocus(target_df:float=0e-9):
    '''
    Set the STEM "intensity" (condenser) defocus component of the microscope in meters.

    Returns
    -------
    : float
        Current intensity defocus value in meters

    '''
    autoscript_microscope.set_stem_intensity_defocus(target_df)
    return autoscript_microscope.get_stem_intensity_defocus()

@mcp.tool()
def get_stem_objective_defocus():
    '''
    Get the STEM objective lens defocus component of the microscope.

    Returns
    -------
    : float
        Current objective defocus value in meters.

    '''
    return autoscript_microscope.get_stem_objective_defocus()

@mcp.tool()
def set_stem_objective_defocus(target_df:float=0e-9):
    '''
    Set the STEM objective lens defocus component of the microscope in meters.

    Returns
    -------
    : float
        Current objective defocus value in meters

    '''
    autoscript_microscope.set_stem_objective_defocus(target_df)
    return autoscript_microscope.get_stem_objective_defocus()


def parse_args():
    parser = argparse.ArgumentParser(
        description='Run the TEAM 0.5 AutoScript-based MCP server.'
    )
    parser.add_argument(
        '--microscope-host',
        default='192.168.0.1',
        help='Microscope AutoScript server hostname (default: 192.168.0.1)'
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    microscope = TemMicroscopeClient()
    microscope.connect(args.microscope_host)

    autoscript_microscope = AutoScriptMicroscope(microscope)

    mcp.run(transport = "http", host = "team05-support.dhcp.lbl.gov", port = 8080)
