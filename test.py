import asyncio
import os
import click
import sys
import json



def port2serdes(port_id):
    with open('./port_config.ini_new','r') as file1:
        raw = file1.read()
        raw_list = raw.split('\n')
        for port_raw in raw_list:
            if port_id in port_raw:
                lanes = port_raw.split(' ')
                lanes = [i for i in lanes if i != ''][1]
                port_speed = port_raw.split(' ')
                port_speed = [i for i in port_speed if i != ''][4]
                print(lanes,port_speed)

    if port_speed == '400000':
        serdes_speed = '50'
    elif port_speed == '100000':
        serdes_speed = '25'
    port_first_lane = lanes.split(',')[0]
    print(port_first_lane)

    with open('./8201.json','r') as file2:
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

# class PRBS(object):
#     def __init__(self):
#         pass
#
# @click.group()
# @click.pass_context
@click.group()
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
def create_prbs_test(tx, rx, prbs_test_start, prbs_test_stop, interface, pattern_type):
    slice, ifg, serdes = port2serdes(interface)
    if pattern_type == "31":
        pattern_type = "PRBS31"
    command = f"""
            mac_port = la_device.get_mac_port({slice}, {ifg}, {serdes})\n
            """
    print(0,"slice,ifg,serdes={},{},{}".format(slice,ifg,serdes))
    print(1,command)
    if tx:
        if prbs_test_start:
            if pattern_type == "NONE":
                click.echo("pattern_type need to be set as 31\n")
                exit()
            command = f"""
                    mac_port.set_serdes_continuous_tuning_enabled(False)\n
                    """
            print(2,command)
            # command = "print(\"slice {}, ifg {}, serdes {}, Err count0: {}, prbs_lock: {}\".format(slice, ifg, serdes, test_info.errors, test_info.prbs_lock))"
            # socketclient.write(command)
            # res = await asyncio.wait_for(socketclient.read(), timeout=5)
            # print(res)
            command = f"""
                    prbs_mode = sdk.la_mac_port.serdes_test_mode_e_{pattern_type}\n \
                    mac_port.set_serdes_test_mode(sdk.la_serdes_direction_e_TX, prbs_mode)\n
                    """
            print(3,command)
        elif prbs_test_stop:
            if pattern_type != "NONE":
                click.echo("pattern_type need to be set as NONE\n")
                exit()
            command = f"""
                    prbs_mode = sdk.la_mac_port.serdes_test_mode_e_{pattern_type}\n \
                    mac_port.set_serdes_test_mode(sdk.la_serdes_direction_e_TX, prbs_mode)\n \
                    mac_port.set_serdes_continuous_tuning_enabled(True)\n
                    """
            print(4,command)
    elif rx:
        if prbs_test_start:
            if pattern_type == "NONE":
                click.echo("pattern_type need to be set as 31\n")
                exit()
            command = f"""
                    mac_port.set_serdes_continuous_tuning_enabled(False)\n
                    """
            print(5,command)

            command = f"""
                    prbs_mode = sdk.la_mac_port.serdes_test_mode_e_{pattern_type}\n \
                    test_info = mac_port.read_serdes_test_ber()\n \
                    mac_port.set_serdes_test_mode(sdk.la_serdes_direction_e_RX, prbs_mode)\n
                    test_info = mac_port.read_serdes_test_ber()\n
                    """
            print(6,command)

            command = "print(\"slice {}, ifg {}, serdes {}, Err count0: {}, prbs_lock: {}\".format(slice, ifg, serdes, test_info.errors, test_info.prbs_lock))"
            print(7,command)
            # res = await asyncio.wait_for(socketclient.read(), timeout=5)
            # print(res)
            # command = "print(\"slice {}, ifg {}, serdes {}, Err count0: {}, prbs_lock: {}\".format(slice, ifg, serdes, test_info.errors, test_info.prbs_lock))"
            # socketclient.write(command)
            # res = await asyncio.wait_for(socketclient.read(), timeout=5)
            # print(res)
            # command = "print(\"slice {}, ifg {}, serdes {}, Err count0: {}, prbs_lock: {}\".format(slice, ifg, serdes, test_info.errors, test_info.prbs_lock))"
            # socketclient.write(command)
            # res = await asyncio.wait_for(socketclient.read(), timeout=5)
            # print(res)
        elif prbs_test_stop:
            if pattern_type != "NONE":
                click.echo("pattern_type need to be set as NONE\n")
                exit()
            command = f"""
                    prbs_mode = sdk.la_mac_port.serdes_test_mode_e_{pattern_type}\n \
                    mac_port.set_serdes_test_mode(sdk.la_serdes_direction_e_RX, prbs_mode)\n \
                    mac_port.set_serdes_continuous_tuning_enabled(True)\n
                    """
            print(7,command)
        pass

prbs_test.add_command(create_prbs_test,name="prbs_test")

if __name__ == '__main__':
    prbs_test()