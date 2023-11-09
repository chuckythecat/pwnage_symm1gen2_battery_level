# requires installation of custom driver using Zadig (outdated)

import winreg as wrg
import usb.core
import usb.backend.libusb1
from pystray import Icon as icon, Menu as menu, MenuItem as item
from PIL import Image
import time
import os

VID = 0x25a7
PID = 0xfa59

msg = [0x08, 0x04, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x49]

isconnected = 0

def kill():
    myicon.stop()
    wrg.SetValueEx(charge, "Value", 0, wrg.REG_SZ, "0")
    os._exit(0)

backend = usb.backend.libusb1.get_backend(find_library=lambda x: r"C:\\libusb-1.0.dll")
dev = usb.core.find(idVendor=VID, idProduct=PID, backend=backend)

if dev is not None:
    print("found")
    isconnected = 1

hwinfo = wrg.CreateKeyEx(wrg.HKEY_CURRENT_USER, r"SOFTWARE\\HWiNFO64\\Sensors\\Custom")

phone = wrg.CreateKeyEx(hwinfo, r"Mouse")

charge = wrg.CreateKeyEx(phone, r"Other0")

wrg.SetValueEx(charge, "Name", 0, wrg.REG_SZ, "Mouse battery")
wrg.SetValueEx(charge, "Value", 0, wrg.REG_SZ, "0")
wrg.SetValueEx(charge, "Unit", 0, wrg.REG_SZ, "/10")

myicon = icon('Phone battery', Image.open(r"C:\\mouse.png"), menu=menu(
    item("Exit", kill, default=True)
))

myicon.run_detached()

while True:
    if isconnected:
        print("send battery request")
        dev.ctrl_transfer(0x21, 0x09, 0x0308, 0x0001, msg)
        try:
            response = dev.read(0x82, 17, 100)
            print(response)
            print(len(response))
            if len(response) == 0:
                print("disconnected")
                isconnected = 0
                dev = usb.core.find(idVendor=VID, idProduct=PID, backend=backend)
                if dev is not None:
                    isconnected = 1
                    print("found")
            else:
                battery = response[6]
                wrg.SetValueEx(charge, "Value", 0, wrg.REG_SZ, str(battery))
                print(f"battery: {battery}")
                print("sleeping for 1h")
                time.sleep(3600)
        except usb.core.USBTimeoutError:
            print("timed out")
    else:
        print("not found")
        dev = usb.core.find(idVendor=VID, idProduct=PID, backend=backend)
        if dev is not None:
            isconnected = 1
            print("found")
        else:
            print("sleeping for 10m")
            time.sleep(600)

# 27:56.542   SendCommand:  08 04 00 00 00 00 00 00 00 00 00 00 00 00 00 00 49

# 27:56.545   Read:  09 04 00 00 00 02 0a 00 00 00 00 00 00 00 00 00 3c