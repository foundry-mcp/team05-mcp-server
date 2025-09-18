# -*- coding: utf-8 -*-
"""
A function that returns templated gatan scripts to call from python.
"""

def dynamic_4D_camera_script(pwidth=256, pheight=256, emd=None, nread=1, rotation=0):
    """ Returns a properly formateed script to acquire a 4D-STEM scan
    using the 4D Camera
    
    Parameters
    ----------
    pwidth: int
    The width of the 4D-STEM scan. This is the fast scan direction
    pheight : int
    The height of the 4D-STEM scan. This is the slow scan direction
    emd: bool
    Deprecated and not used
    nread:int
    The number of frames to acquire at each probe position
    rotation: float
    The STEM rotation in degrees.
    
    Returns
    -------
    : str
    The string with the parameters written in the format of a DM script.
    
    """
    script_text =  f"""// Acquire a 4D camera scan.

        string command, ipAddressPlusPort, reply
        TagGroup DLG, DLGItems

        // Digiscan user variables
        number rotation = {rotation} // degree, 0 matches FEI software
        number width = {pwidth}  // pixel, final 4D scan image is width + 1
        number height = {pheight} // pixel

        // 4D Camera user varibales
        number nread = {nread} // frames per scan position
        number nskip = 0 // number to skip between probe positions
        number nflyback = 300 // typically this is set to 300 (# frames for flyback time)

        // Other system variables
        number dataType = 4 // 4 byte data
        number signalIndex = 0
        number pixelTime= 10 // microseconds, only for HAADF
        number lineSync = 0 //

        number write_to_file = 1 // not implemented; use to fill ram with multiple scans in a row
        Number timeout_s = 10.0 // TCP/IP receive timeout

        // IP address must be a IPv4 set of numbers.
        ipAddressPlusPort = "131.243.3.25:42003" // the format is quad IP address, colon, port number.

        // User must synchronize with 4D Camera output manually
        // SetPersistentNumberNote("4D_scannum", XXX)  //example. copy to new script and run
        number scan_number
        GetPersistentNumberNote("4D_scannum", scan_number)

        EMSetScreenPosition(2)
        EMSetBeamBlanked(1)
        sleep(0.1)

        // update the dark image
        command = "enabledarkfieldsub 2 0 20" // enable and retake, threshold, offset
        SocketConnect(ipAddressPlusPort)
        reply = SocketSendStringGetReply(ipAddressPlusPort, command, timeout_s)  //send string and wait for reply
        SocketDisconnect(ipAddressPlusPort)  // this is optional
        sleep(0.5)

        //
        // Acquire Data
        //

        dssetexternalpixelclock(1) // 1 for 4D Camera

        // Setup scan parameters
        //Number DSCreateParameters( Number width, Number height, Number rotation, Number pixelTime, Boolean lineSynchEnabled )
        number p = DSCreateParameters(width, height, rotation, pixelTime, 0)

        // Connect to HAADF
        //Boolean DSSetParametersSignal( Number paramID, Number signalIndex, Number dataType, Boolean selected, Number imageID )
        DSSetParametersSignal(p, signalIndex, 4, 1, 0)

        EMSetBeamBlanked(0)
        sleep(0.1)

        // Start the acquisition
        //void DSStartAcquisition( Number paramID, Boolean continuous, Boolean synchronous )
        // synchronoys = 0 to return immediately allowing 4D camerat to start the scan
        DSStartAcquisition(p, 0, 0)

        //Start STEM scan on 4D camera
        //StartSTEMScan <npause> <nread> <nSTEMx> <nSTEMrows> <nflyback> <write_to_file> (all must be >=0)
        command = "startstemscan " + nskip + " " + nread + " " + (width + 1) + " " + height + " " + nflyback + " 1"
        SocketConnect(ipAddressPlusPort)
        reply = SocketSendStringGetReply(ipAddressPlusPort, command, timeout_s)  //send string and wait for reply
        DSWaitUntilFinished()

        // Move this after DSWaitUntilFinished to make it more stable
        SocketDisconnect(ipAddressPlusPort)  // this is optional
        result(reply)

        EMSetBeamBlanked(1)

        image image0 := GetFrontImage()

        dssetexternalpixelclock(0) // 0 for normal
        DSDeleteParameters(p)

        // Change the name of the image and add metadata
        TagGroup tg = image0.ImageGetTagGroup()
        number index
        taggroup tg_4d = tg.TagGroupCreateNewLabeledGroup("4Dcamera Parameters")
        index = tg_4d.TagGroupCreateNewLabeledTag("npause")
        tg_4d.TagGroupSetIndexedTagAsFloat( index, npause)
        index = tg_4d.TagGroupCreateNewLabeledTag("nread")
        tg_4d.TagGroupSetIndexedTagAsFloat( index, nread)
        index = tg_4d.TagGroupCreateNewLabeledTag("nskip")
        tg_4d.TagGroupSetIndexedTagAsFloat( index, nskip)
        index = tg_4d.TagGroupCreateNewLabeledTag("nflyback")
        tg_4d.TagGroupSetIndexedTagAsFloat( index, nflyback)
        index = tg_4d.TagGroupCreateNewLabeledTag("scan_number")
        tg_4d.TagGroupSetIndexedTagAsNumber( index, scan_number)

        SetName(image0, "scan" + scan_number)

        // Automatically save data to sync directory
        SaveAsGatan(image0, "X:\\scan" + scan_number + ".dm4")

        // For server to read and return
        SaveAsGatan(image0, "C:\\\\Users\\\\VALUEDGATANCUSTOMER\\\\Documents\\\\automation\\\\latest_4Dscan.dm4")

        SetPersistentNumberNote("4D_scannum", scan_number+1)

        result("4Dcamera scan done\\n")
        """
    return script_text
    
def dynamic_4D_camera_script(dwell_time=1e-6, pwidth=256, pheight=256, rotation=0):
    """ Returns a properly formateed script to acquire a SSTEM scan
    using the HAADF detector.
    
    Parameters
    ----------
    dwell_time : float
    The dwell time in seconds.
    pwidth: int
    The width of the 4D-STEM scan. This is the fast scan direction
    pheight : int
    The height of the 4D-STEM scan. This is the slow scan direction
    nread:int
    The number of frames to acquire at each probe position
    rotation: float
    The STEM rotation in degrees.
    
    Returns
    -------
    : str
    The string with the parameters written in the format of a DM script.
    
    """
    script_text =  f"""//Acquire a STEM image
    // Setup scan parameters
    // Digiscan
    number dataType = 4 // 4 byte data
    number width = {pwidth} // pixel, final 4D scan image is width + 1
    number height = {pheight} // pixel

    number signalIndex = 0
    number rotation = {rotation} // degree, 0 matches FEI software
    number pixelTime= {dwell_time}*1e6 // microseconds
    number lineSync = 0 //

    //Number DSCreateParameters( Number width, Number height, Number rotation, Number pixelTime, Boolean lineSynchEnabled )
    number p = DSCreateParameters(width, height, rotation, pixelTime, 0)

    // Connect to HAADF
    //Boolean DSSetParametersSignal( Number paramID, Number signalIndex, Number dataType, Boolean selected, Number imageID )
    DSSetParametersSignal(p, signalIndex, 4, 1, 0)

    // Start the acquisition
    //void DSStartAcquisition( Number paramID, Boolean continuous, Boolean synchronous )
    // synchronoys = 0 to return immediately allowing 4D camerat to start the scan
    DSStartAcquisition(p, 0, 0)

    image image0 := GetFrontImage()

    dssetexternalpixelclock(0) // 0 for normal
    DSDeleteParameters(p)

    // For server to read and return
    SaveAsGatan(image0, "C:\\\\Users\\\\VALUEDGATANCUSTOMER\\\\Documents\\\\automation\\\\latest_HAADF_scan.dm4")

    result("HAADF scan done\\n")
    """
    return script_text

//Acquire a STEM image
// Setup scan parameters
// Digiscan
number dataType = 4 // 4 byte data
number width = {width} // pixel, final 4D scan image is width + 1
number height = {height} // pixel

number signalIndex = 0
number rotation = {rotation} // degree, 0 matches FEI software
number pixelTime= {dwell_time} // microseconds, only for HAADF
number lineSync = 0 //

//Number DSCreateParameters( Number width, Number height, Number rotation, Number pixelTime, Boolean lineSynchEnabled )
number p = DSCreateParameters(width, height, rotation, pixelTime, 0)

// Connect to HAADF
//Boolean DSSetParametersSignal( Number paramID, Number signalIndex, Number dataType, Boolean selected, Number imageID )
DSSetParametersSignal(p, signalIndex, 4, 1, 0)

// Start the acquisition
//void DSStartAcquisition( Number paramID, Boolean continuous, Boolean synchronous )
// synchronoys = 0 to return immediately allowing 4D camerat to start the scan
DSStartAcquisition(p, 0, 0)

image image0 := GetFrontImage()

