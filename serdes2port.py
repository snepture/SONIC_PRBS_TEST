import json

port_id = 'Ethernet4'

if __name__ == '__main__':
    with open('./port_config.ini','r') as file1:
        raw = file1.read()
        raw_list = raw.split('\n')
        for port_raw in raw_list:
            if port_id in port_raw:
                lanes = port_raw.split('    ')[1].strip()
                port_speed = port_raw.split('    ')[4].strip()
                # print(lanes,port_speed)

    if port_speed == '400000':
        serdes_speed = '50'
    elif port_speed == '100000':
        serdes_speed = '25'
    port_first_lane = lanes.split(',')[0]
    # print(port_first_lane)

    with open('./8201_p4.json','r') as file2:
        serdes_raw = json.loads(file2.read())
        port_mix = serdes_raw['devices'][0]['port_mix']['ports']
        for item in port_mix:
            if str(hex(int(port_first_lane))) in item['pif']:
                port_media = item['media_type']


        serdes_keys= serdes_raw['devices'][0]['serdes_params'].keys()
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