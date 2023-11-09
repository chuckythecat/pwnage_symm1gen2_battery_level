import pywinusb.hid as hid
from time import sleep

request_battery_level_message = [0x04, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x49]
request_mouse_state =           [0x03, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x4a]

# VID and PID is for Zet Gaming Prime Pro Wireless V2 (PAW3370)
# (pretty sure just a OEM Pwnage Ultra Custom Wireless Symm 1 Gen 2)
vid = 0x25a7
pid = 0xfa59

received = False
def sample_handler(data):
    global received
    print(f"Received: {data}")
    if data[1] == 3:
        print("Type: mouse state")
        if data[6] == 0:
            print("Dongle is connected but mouse is not responding. \nBattery level may report as 0% if mouse was never moved after dongle was connected.")
    elif data[1] == 4:
        print("Type: battery level")
        print(f"Battery level: {data[6]*10}%")
        received = True

# find target device
all_hids = hid.HidDeviceFilter(vendor_id = vid, product_id = pid).get_devices()
target_usage = hid.get_full_usage_id(0xff02, 0x02)
# if found
if all_hids:
    # search for send and receive device
    for index, device in enumerate(all_hids):
        if "hid#vid_25a7&pid_fa59&mi_01&col07" in device.device_path:
            send_device = all_hids[index]
        if "hid#vid_25a7&pid_fa59&mi_01&col05" in device.device_path:
            recv_device = all_hids[index]
    # open both
    try:
        send_device.open()
        recv_device.open()

        # set received data handler
        recv_device.set_raw_data_handler(sample_handler)

        print("\nWaiting for data...")

        # find target usage
        for report in send_device.find_output_reports() + send_device.find_feature_reports():
            if target_usage in report:
                # set target usage message
                report[target_usage] = request_mouse_state
                # validate that message was set
                new_raw_data = report.get_raw_data()
                # send battery level request
                report.set_raw_data( new_raw_data )
                report.send()
                print("Battery level report sent")


                # set target usage message
                report[target_usage] = request_battery_level_message
                # validate that message was set
                new_raw_data = report.get_raw_data()
                # send mouse state request
                report.set_raw_data( new_raw_data )
                report.send()
                print("Mouse state report sent")
        
        # wait for the battery level answer to be received by handler
        while not received: pass
    finally:
        send_device.close()
        recv_device.close()
