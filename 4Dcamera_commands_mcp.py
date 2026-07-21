
import os
import socket
import paramiko
from fastmcp import FastMCP
from dotenv import load_dotenv

mcp = FastMCP("4Dcamera")

# Load environment variables from .env file
load_dotenv()
# Define the server's IP address and port
server_host = os.getenv("SRV_HOST") # the address of the server to send the commands
server_user = os.getenv("SRV_USR") # the username to log into the server
server_pwd = os.getenv("SRV_PWD")
server_port = os.getenv("SRV_PORT") # the port to send the commands to
# 4D Camera head IP address and credentials
camera_ip = os.getenv("CAM_IP") # the camera head IP
camera_usr = os.getenv("CAM_USR")
camera_pwd = os.getenv("CAM_PWD2")

def ssh_connect_with_password(hostname, username, password, command):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        client.connect(hostname, username=username, password=password)
        stdin, stdout, stderr = client.exec_command(command)
        result = stdout.read().decode()
        error = stderr.read().decode()
        print(result)
        print(error)
        return result
    except Exception as e:
        error_msg = f"SSH connection failed: {str(e)}"
        print(error_msg)
        return error_msg
    finally:
        client.close()

def send_command(content):
    """ This function takes in a string as a command to the 4D Camera. 
    Parameters
    ----------
    content : str
        The command to send to the 4D Camera server as a string.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((server_host, int(server_port)))
    s.sendall(content.encode())
    s.shutdown(socket.SHUT_WR)
    while True:
        data = s.recv(4096)
        if not data:
            break
        print(str(data.decode()))

    s.close()


@mcp.tool()
def on_new_dark(mode=2, threshold=0, offset=20):
    """This function acquires a new dark image for the camera. It has 
    inputs that allow you to modify the final image such as a threshold, 
    and offset. 
    
    Parameters
    ----------
    mode : int
        The mode can be either 0, 1, or 2
        0 - the dark subtraction is turned off
        1 - the dak subtraction is turned on
        2 - a new dark image is acquired and then dark subtraction is turned on
    threshold : int
        All values below this integer will automatically be set to 0.
    offset : int
        An offset to apply to every image. Typically this is 20 to allow the
        full Gaussian noise profile to be shown in a uint16 dataset.
    """
    content = f"enabledarkfieldsub {mode} {threshold} {offset}"
    send_command(content)

@mcp.tool()
def on_resync():
    """This will run the syncing routine on the camera head which 
    syncs the camera head and the FPGAs. It will also reset the scan number.
    """
    content = "resync"
    send_command(content)

@mcp.tool()
def on_power_down():
    """This will run the power down script on the camera head effectively shutting down the camera.
    
    Always confirm with the user that they want to power down the camera before running this command.
    The camera will need to be powered up again before it can be used.
    """
    content = "powerdowncamera"
    send_command(content)

@mcp.tool()
def on_power_up(set_temperature=True):
    """This will run the power up script on the camera head.
    This will start up the camera so it is ready for operation.

    This script has a line that sets the sensor temperature to -10C. 
    This will usually fail due to the camera cooling too fast.
    It is suggested to automatically set the temperature to 19C after powering up. 
    Then the user should manually cool down in -5C increments to -10C. 
    This will allow the camera to cool down without failing.

    Parameters
    ----------
    set_temperature : bool
        Set this to True to set the sensor temperature to 19C after
        powering up. Otherwise, the temperature is set to -10C and cooling fails.
    """
    content = "powerupcamera"
    send_command(content)

    if set_temperature:
        content = f"setsensortemperature 19"
        send_command(content)

@mcp.tool()
def on_set_temperature(temperature=None):
    """Set the sensor temperature of the 4D Camera. The 
    temperature is in celsius. Possible values are between -10C and 19C non-inclusive.
    The camera is normally operated when the temperature is at -9.9C."""
    content = f"setsensortemperature {temperature}"
    send_command(content)

@mcp.tool()
def on_get_temperature():
    """This reads the temperature from the sensor. Only the Q1 temperature is important."""
    command1 = f"echo \"dsh sensor temp\" | sshpass -p {camera_pwd} ssh -T -o HostKeyAlgorithms=ssh-rsa {camera_usr}@{camera_ip}"
    rr = ssh_connect_with_password(server_host, server_user, server_pwd, command1)
    return(rr)

@mcp.tool()
def start_stem_scan(width, height, npause=0, nread=1, flyback=300):
    '''Take a data set with the 4D Camera.
    
    Parameters
    ----------
    width : int
        The width of the scan area.
    height : int
        The height of the scan area.
    npause : int
        The number of frames to pause between acquisition at each position. This slows
        down the rate of frame acquisition allowing time for processing.
    nread : int
        The number of frames to read at each scan position. This is typically 1, but can be increased to average multiple frames effectively increasing the exposure time.
    flyback : int
        The flyback time. The number of frames to wait after a scan line is completed before starting the next scan line.

    '''
    command = f"startstemscan {npause} {nread} {width} {height} {flyback} 1"
    send_command(command)

@mcp.tool()
def insert_camera():
    ''' Insert 4D Camera into beam path.'''
    send_command('insertcamera')


@mcp.tool()
def retract_camera():
    '''Retract 4D Camera from beam path.'''
    send_command('retractcamera')


if __name__ == "__main__":
    # mcp.run(transport = "sse", port = 8003)
    mcp.run(transport = "sse", host = "team05-support.dhcp.lbl.gov", port = 8083)
