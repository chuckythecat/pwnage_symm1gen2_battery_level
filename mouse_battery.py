import pywinusb.hid as hid
from time import sleep

request_battery_level_message = [0x04, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x49]
request_mouse_state =           [0x03, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x4a]

# Zet Gaming Prime Pro Wireless V2 (PAW3370)
vid = 0x25a7
# wireless dongle
pid = 0xfa59
# wired connection
# pid = 0xfa5a

# Pwnage Ultra Custom Symm 1 Gen 2 (not sure, pulled from official pwnage software)
# wireless dongle
# pid = 0xfa7c
# wired connection
# pid = 0xfa7b

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

def checkBattery(send_device, recv_device, target_usage, handler):
    # set received data handler
    # recv_device.set_raw_data_handler(sample_handler)

    print("\nWaiting for data...")

    # find target usage
    for report in send_device.find_output_reports() + send_device.find_feature_reports():
        if target_usage in report:
            # set target usage message
            report[target_usage] = request_battery_level_message
            # validate that message was set
            new_raw_data = report.get_raw_data()
            print(new_raw_data)
            # send battery level request
            report.set_raw_data( new_raw_data )
            report.send()
            print("Battery level report sent")

# find target device
all_hids = hid.HidDeviceFilter(vendor_id = vid, product_id = pid).get_devices()
target_usage = hid.get_full_usage_id(0xff02, 0x02)
# if found
if all_hids:
    # search for send and receive device
    for index, device in enumerate(all_hids):
        if "hid#vid_" + str(hex(vid))[2:] + "&pid_" + str(hex(pid))[2:] + "&mi_01&col07" in device.device_path:
            send_device = all_hids[index]
        if "hid#vid_" + str(hex(vid))[2:] + "&pid_" + str(hex(pid))[2:] + "&mi_01&col05" in device.device_path:
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
                print("Mouse state report sent")

                sleep(2)

                # set target usage message
                report[target_usage] = request_battery_level_message
                # validate that message was set
                new_raw_data = report.get_raw_data()
                # send mouse state request
                report.set_raw_data( new_raw_data )
                report.send()
                print("Battery level report sent")
        
        # wait for the battery level answer to be received by handler
        while not received: pass
    except NameError:
        print("error: target device was found but target usages were not")
    finally:
        # send_device.close()
        # recv_device.close()
        pass