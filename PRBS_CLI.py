#!/usr/bin/env python3

import asyncio
import os
import click
import sys
import json
import re
from functools import wraps

SAI_DEBUG_SHELL_URI_SAI = '/var/run/sai_debug_shell.sock'
SAI_DEBUG_SHELL_URI_S1 = '/var/run/s1_debug_shell.sock'
LEABA_VALIDATION_PATH_DEFAULT = '/usr/lib/cisco/pylib/leaba'
LEABA_SDK_PATH_DEFAULT = '/usr/lib/cisco/pylib/leaba'
dir = os.path.split(os.path.realpath(__file__))[0]
PORT_CONFIG_PATH = '/usr/share/sonic/hwsku/port_config.ini'
SERDES_JSON_PATH = '/usr/share/sonic/hwsku/8201.json'

HOST = '127.0.0.1'
PORT = 10000

def coro(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not asyncio.get_event_loop().is_running():
            return asyncio.run(f(*args, **kwargs))
        else:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(f(*args, **kwargs))
    return wrapper

class SocketClient(object):
    def __init__(self):
        self.writer = None
        self.reader = None

    async def connect_with_port(self, host, port):
        self.reader, self.writer = await asyncio.open_connection(host, port)
        # print("Connected to {}:{}".format(host, port))

    async def connect_with_unix(self, unix_file):
        self.reader, self.writer = await asyncio.open_unix_connection(unix_file)
        # print("Connected to {}".format(unix_file))

    async def read(self):
        res = ""
        if self.reader:
            try:
                data = await self.reader.readline()
            except (BrokenPipeError, IOError):
                print("Pipe broken, being occupied！")
                sys.exit()

            if data.decode('utf-8'):
                res = data.decode('utf-8').replace('>>>', '').strip()
            else:
                res = data.decode('utf-8').strip()
        return res

    def write(self, message):
        if self.writer:
            message = message + '\n'
            # print("send:{}".format(message))
            self.writer.write(message.encode('utf-8'))
            # await self.writer.drain()

    async def close(self):
        self.writer.close()


async def connect(socketclient):
    basename_SAI = os.path.splitext(os.path.basename(SAI_DEBUG_SHELL_URI_SAI))[0]
    basename_S1 = os.path.splitext(os.path.basename(SAI_DEBUG_SHELL_URI_S1))[0]
    output = os.popen('netstat -an').read()
    for line in output.splitlines():
        if re.match("unix.*%s.*" % basename_SAI, line):
            try:
                await asyncio.wait_for(socketclient.connect_with_unix(SAI_DEBUG_SHELL_URI_SAI), timeout=10)
                return True
            except Exception as e:
                print("Timeout connecting unix.")

        if re.match("tcp.*12345.*LISTEN", line):
            try:
                if await asyncio.wait_for(socketclient.connect_with_port(HOST, PORT), timeout=2):
                    return True
            except asyncio.TimeoutError:
                print("Timeout connecting port.")


async def buf_read(socketclient, t):
    lost_count = 0
    while True:
        try:
            msg = await asyncio.wait_for(socketclient.read(), timeout=t)
            if msg == b"":
                lost_count += 1
                if lost_count >= 10:
                    raise ConnectionAbortedError
            print(msg)
        except asyncio.TimeoutError:
            break

async def check_init(socketclient):
    LEABA_SDK_PATH = "/usr/lib/cisco/pylib/leaba"
    LEABA_VALIDATION_PATH = "/usr/lib/cisco/pylib/leaba/debug_tools/hw_tables/lpm"
    init_pack = """
                    import sys\n
                    import os\n
                    sys.path.append(\"{}/..\")\n
                    sys.path.append(\"{}\")\n
                    sys.path.append(\"{}/debug_tools\")\n
                    sys.path.append(\"{}/debug_tools/hw_tables/lpm\")\n
                    sys.LEABA_SDK_PATH=\"{}\"\n
                    sys.LEABA_VALIDATION_PATH=\"{}\"\n 
                    sys.path.append(sys.LEABA_VALIDATION_PATH)\n 
                    sys.path.append(sys.LEABA_SDK_PATH)\n
                    from leaba import sdk\n
                    la_device = sdk.la_get_device(0)\n
                    from leaba_val import *\n
                    os.environ['BASE_OUTPUT_DIR'] = \"/opt/cisco/silicon-one/\"\n 
                    set_dev(la_device)\n 
                    from leaba.debug_api import *\n
                    dapi = DebugApi()\n
                    from leaba.dbg import *\n 
                    dbg=dbg_dev(la_device)\n
                    """.format(LEABA_SDK_PATH,LEABA_SDK_PATH,LEABA_SDK_PATH,LEABA_SDK_PATH,LEABA_SDK_PATH,LEABA_VALIDATION_PATH)

    eg = "print('{}/debug_tools' in sys.path)\n".format(LEABA_SDK_PATH)
    try:
        socketclient.write(eg)
    except Exception as e:
        print("Error: " + str(e))
    while True:
        if socketclient.reader:
            res = await asyncio.wait_for(socketclient.read(), timeout=5)
            if "True" in res or "sys" in res:
                break
        else:
            print("Connection error, Quit!")
            sys.exit()

    if "True" in res:
        # print("Packets are already loaded.")
        print("")
    else:
        for line in init_pack.split('\n'):
            command = line.strip() + '\n'
            socketclient.write(command)
        print("***First time run***\nPlease wait for a moment until packages are loaded...")
        lost_count = 0
        while True:
            data = await socketclient.reader.readline()
            if data == b"":
                lost_count += 1
                if lost_count >= 10:
                    raise ConnectionAbortedError
        # await asyncio.sleep(10)

def port2serdes(port_id):
    with open(PORT_CONFIG_PATH,'r') as file1:
        raw = file1.read()
        raw_list = raw.split('\n')
        for port_raw in raw_list:
            if port_id in port_raw:
                lanes = port_raw.split(' ')
                lanes = [i for i in lanes if i != ''][1]
                port_speed = port_raw.split(' ')
                port_speed = [i for i in port_speed if i != ''][4]
                # print(lanes,port_speed)

    if port_speed == '400000':
        serdes_speed = '50'
    elif port_speed == '100000':
        serdes_speed = '25'
    port_first_lane = lanes.split(',')[0]
    # print(port_first_lane)

    with open(SERDES_JSON_PATH,'r') as file2:
        serdes_raw = json.loads(file2.read())
        port_mix = serdes_raw['devices'][0]['port_mix']['ports']
        for item in port_mix:
            if str(hex(int(port_first_lane))) in item['pif']:
                port_media = item['media_type']

        serdes_keys = serdes_raw['devices'][0]['serdes_params'].keys()
        for key in serdes_keys:
            if 'COPPER' in key or 'OPTIC' in key:
                slice_id = key.split(',')[0]
                ifg_id = key.split(',')[1]
                serdes_id = key.split(',')[2]
                speed = key.split(',')[3]
                media = key.split(',')[4]
                first_lane_num = int((int(slice_id) * 2 + int(ifg_id)) * (0x100) + int(serdes_id))

                if int(port_first_lane) == first_lane_num and port_media == media and serdes_speed == speed:
                    final_slice_id = key.split(',')[0]
                    final_ifg_id = key.split(',')[1]
                    final_serdes_id = key.split(',')[2]
    return final_slice_id, final_ifg_id, final_serdes_id

async def initsock():
    sock = SocketClient()
    await connect(sock)
    try:
        await asyncio.wait_for(check_init(sock), timeout=20)
    except asyncio.TimeoutError:
        print("Init timeout, please try again.")
        sys.exit(0)
    return sock

@click.group(context_settings=dict(ignore_unknown_options=True))
def prbs_test():
    pass

@click.command()
@click.option(
    "--tx",
    is_flag = True,
    help = "define the port type to TX"
)
@click.option(
    "--rx",
    is_flag = True,
    help = "define the port type to RX"
)
@click.option(
    "--prbs_test_start",
    is_flag = True,
    help = "define the status to start"
)
@click.option(
    "--prbs_test_stop",
    is_flag = True,
    help = "define the status to stop"
)
@click.option(
    "--interface",
    required = True,
    type = str,
    help = "define the interface"
)
@click.option(
    "--pattern_type",
    required = True,
    default = "31",
    help = "define the pattern type(default 31)"
)

@coro
async def create_prbs_test(tx, rx, prbs_test_start, prbs_test_stop, interface, pattern_type):
    socketclient = await initsock()
    slice, ifg, serdes = port2serdes(interface)
    if pattern_type == "31":
        pattern_type = "PRBS31"
    command = "slice,ifg,serdes = {},{},{}\n".format(slice, ifg, serdes)
    socketclient.write(command)
    print(f"Interface {interface}: slice {slice}, ifg {ifg}, serdes {serdes}\n [{command.strip()}]\n")
    await asyncio.sleep(1)
    command = "mac_port = la_device.get_mac_port({}, {}, {})\n".format(slice, ifg, serdes)
    socketclient.write(command)
    print(f"Setting mac port...\n[{command.strip()}]\n")
    await asyncio.sleep(1)

    # command = "mac_port\n"
    # socketclient.write(command)
    # print("Command writing: " + command + "\n")
    # res = await socketclient.read()
    # print("res:"+res)

    if tx:
        if prbs_test_start:
            if pattern_type == "NONE":
                click.echo("pattern_type need to be set as 31\n")
                exit()
            command = "mac_port.set_serdes_continuous_tuning_enabled(False)\n"
            socketclient.write(command)
            print(f"Mac port serdes continuous tuning setting to False...\n[{command.strip()}]\n")
            await asyncio.sleep(1)
            command = "prbs_mode = sdk.la_mac_port.serdes_test_mode_e_{}\n".format(pattern_type)
            socketclient.write(command)
            print(f"Setting serdes mode to {pattern_type} ...\n[{command.strip()}]\n")
            await asyncio.sleep(1)
            command = "mac_port.set_serdes_test_mode(sdk.la_serdes_direction_e_TX, prbs_mode)\n"
            socketclient.write(command)
            print(f"Setting mac port to PRBS test TX with mode {pattern_type} ... \n[{command.strip()}]\n")
            await asyncio.sleep(1)
        elif prbs_test_stop:
            if pattern_type != "NONE":
                click.echo("pattern_type need to be set as NONE\n")
                exit()
            command = "prbs_mode = sdk.la_mac_port.serdes_test_mode_e_{}\n".format(pattern_type)
            socketclient.write(command)
            print(f"Setting serdes mode to {pattern_type} ...\n[{command.strip()}]\n")
            await asyncio.sleep(1)
            command = "mac_port.set_serdes_test_mode(sdk.la_serdes_direction_e_TX, prbs_mode)\n"
            socketclient.write(command)
            print(f"Setting mac port to PRBS test TX with mode {pattern_type} ... \n[{command.strip()}]\n")
            await asyncio.sleep(1)
            command = "mac_port.set_serdes_continuous_tuning_enabled(True)\n"
            socketclient.write(command)
            print(f"Mac port serdes continuous tuning setting to True...\n[{command.strip()}]\n")
            await asyncio.sleep(1)
    elif rx:
        if prbs_test_start:
            if pattern_type == "NONE":
                click.echo("pattern_type need to be set as 31\n")
                exit()
            command = "mac_port.set_serdes_continuous_tuning_enabled(False)\n"
            socketclient.write(command)
            print(f"Mac port serdes continuous tuning setting to False...\n[{command.strip()}]\n")
            await asyncio.sleep(1)
            command = "prbs_mode = sdk.la_mac_port.serdes_test_mode_e_{}\n".format(pattern_type)
            socketclient.write(command)
            print(f"Setting serdes mode to {pattern_type} ...\n[{command.strip()}]\n")
            await asyncio.sleep(1)
            command = "test_info = mac_port.read_serdes_test_ber()\n"
            socketclient.write(command)
            print(f"Refreshing serdes test status...\n[{command.strip()}]\n")
            await asyncio.sleep(1)
            command = "mac_port.set_serdes_test_mode(sdk.la_serdes_direction_e_RX, prbs_mode)\n"
            socketclient.write(command)
            print(f"Setting mac port to PRBS test RX with mode {pattern_type} ... \n[{command.strip()}]\n")
            await asyncio.sleep(1)
            command = "test_info = mac_port.read_serdes_test_ber()\n"
            socketclient.write(command)
            print(f"Refreshing serdes test status...\n[{command.strip()}]\n")
            await asyncio.sleep(1)

            command = "print(\"slice {}, ifg {}, serdes {}, Err count0: {}, prbs_lock: {}\".format(slice, ifg, serdes, test_info.errors, test_info.prbs_lock))"
            socketclient.write(command)
            print(f"[{command.strip()}]\n")
            await asyncio.sleep(1)
            res = await asyncio.wait_for(socketclient.read(), timeout=5)
            print(f">>> {res}\n")
            await asyncio.sleep(1)
            command = "print(\"slice {}, ifg {}, serdes {}, Err count0: {}, prbs_lock: {}\".format(slice, ifg, serdes, test_info.errors, test_info.prbs_lock))"
            socketclient.write(command)
            print(f"[{command.strip()}]\n")
            await asyncio.sleep(1)
            res = await asyncio.wait_for(socketclient.read(), timeout=5)
            print(f">>> {res}\n")
            await asyncio.sleep(1)
            command = "print(\"slice {}, ifg {}, serdes {}, Err count0: {}, prbs_lock: {}\".format(slice, ifg, serdes, test_info.errors, test_info.prbs_lock))"
            socketclient.write(command)
            print(f"[{command.strip()}]\n")
            await asyncio.sleep(1)
            res = await asyncio.wait_for(socketclient.read(), timeout=5)
            print(f">>> {res}\n")
            await asyncio.sleep(1)
        elif prbs_test_stop:
            if pattern_type != "NONE":
                click.echo("pattern_type need to be set as NONE\n")
                exit()
            command = "prbs_mode = sdk.la_mac_port.serdes_test_mode_e_{}\n"
            socketclient.write(command)
            print(f"Setting serdes mode to {pattern_type} ...\n[{command.strip()}]\n")
            await asyncio.sleep(1)
            command = "mac_port.set_serdes_test_mode(sdk.la_serdes_direction_e_RX, prbs_mode)\n"
            socketclient.write(command)
            print(f"Setting mac port to PRBS test RX with mode {pattern_type} ... \n[{command.strip()}]\n")
            await asyncio.sleep(1)
            command = "mac_port.set_serdes_continuous_tuning_enabled(True)\n"
            socketclient.write(command)
            print(f"Mac port serdes continuous tuning setting to True...\n[{command.strip()}]\n")
            await asyncio.sleep(1)

prbs_test.add_command(create_prbs_test,name="prbs_test")


if __name__ == '__main__':

    try:
        prbs_test()
    except Exception as e:
        print("Error: " + str(e))

    except KeyboardInterrupt:
        print("\nKeyboardInterrupt, Quit!")
    except ConnectionAbortedError:
        print("Connection lost, Quit!")