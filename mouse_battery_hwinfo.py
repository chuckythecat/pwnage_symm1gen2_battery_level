# https://abdus.dev/posts/python-monitor-usb/
import win32api, win32con, win32gui
import pywinusb.hid as hid
from PIL import Image
from pystray import Icon as icon, Menu as menu, MenuItem as item
import winreg as wrg
import threading
import os
import mouse

# VID and PIDs is for Zet Gaming Prime Pro Wireless V2 (PAW3370)
# (pretty sure just a OEM Pwnage Ultra Custom Wireless Symm 1 Gen 2)
vid = 0x25a7
pid_wireless = 0xfa59
pid_wired = 0xfa5a

# Pwnage Ultra Custom Symm 1 Gen 2 (not sure, pulled from official pwnage software)
# wireless dongle
# pid = 0xfa7c
# wired connection
# pid = 0xfa7b

checkEvery = 3600

class DeviceListener:
    """
    Listens to Win32 `WM_DEVICECHANGE` messages
    and trigger a callback when a device has been plugged in or out

    See: https://docs.microsoft.com/en-us/windows/win32/devio/wm-devicechange
    """
    WM_DEVICECHANGE_EVENTS = {
        0x0019: ('DBT_CONFIGCHANGECANCELED', 'A request to change the current configuration (dock or undock) has been canceled.'),
        0x0018: ('DBT_CONFIGCHANGED', 'The current configuration has changed, due to a dock or undock.'),
        0x8006: ('DBT_CUSTOMEVENT', 'A custom event has occurred.'),
        0x8000: ('DBT_DEVICEARRIVAL', 'A device or piece of media has been inserted and is now available.'),
        0x8001: ('DBT_DEVICEQUERYREMOVE', 'Permission is requested to remove a device or piece of media. Any application can deny this request and cancel the removal.'),
        0x8002: ('DBT_DEVICEQUERYREMOVEFAILED', 'A request to remove a device or piece of media has been canceled.'),
        0x8004: ('DBT_DEVICEREMOVECOMPLETE', 'A device or piece of media has been removed.'),
        0x8003: ('DBT_DEVICEREMOVEPENDING', 'A device or piece of media is about to be removed. Cannot be denied.'),
        0x8005: ('DBT_DEVICETYPESPECIFIC', 'A device-specific event has occurred.'),
        0x0007: ('DBT_DEVNODES_CHANGED', 'A device has been added to or removed from the system.'),
        0x0017: ('DBT_QUERYCHANGECONFIG', 'Permission is requested to change the current configuration (dock or undock).'),
        0xFFFF: ('DBT_USERDEFINED', 'The meaning of this message is user-defined.'),
    }

    def __init__(self, vendor_id, product_id_wired, product_id_wireless, checkEvery):
        # interval between scheduled battery level checks
        self.checkEvery = checkEvery
        # vid and pids
        self.vendor_id = vendor_id
        self.product_id_wired = product_id_wired
        self.product_id_wireless = product_id_wireless
        # flag which is used to determine if incoming events are related to mouse:
        # if flag is True and event is received event is ignored (mouse is still connected,
        # event is related to some other device)
        # if flag is False and event is received redefine send_device and recv_device
        # objects, check battery level again and reenable scheduled device check
        self.isConnected = False
        self.request_battery_level_message = [0x04, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x49]
        # flag set to True by 
        # self.received = False
        self.dir_path = os.path.dirname(os.path.realpath(__file__))
        self.hwinfo = wrg.CreateKeyEx(wrg.HKEY_CURRENT_USER, r"SOFTWARE\\HWiNFO64\\Sensors\\Custom")
        self.mouse = wrg.CreateKeyEx(self.hwinfo, r"Mouse")
        self.charge = wrg.CreateKeyEx(self.mouse, r"Other0")
        self.nextTimer = threading.Timer(self.checkEvery, self.timerChecker)
        wrg.SetValueEx(self.charge, "Name", 0, wrg.REG_SZ, "Mouse battery")
        wrg.SetValueEx(self.charge, "Value", 0, wrg.REG_SZ, "0")
        wrg.SetValueEx(self.charge, "Unit", 0, wrg.REG_SZ, "/10")

        self.myicon = icon('Mouse battery', Image.open(fr"{self.dir_path}\\mouse.png"), "Mouse battery", menu=menu(
            item("Exit", self.kill, default=True)
        ))

        self.myicon.run_detached()
        self.on_change()

    def _create_window(self):
        """
        Create a window for listening to messages
        https://docs.microsoft.com/en-us/windows/win32/learnwin32/creating-a-window#creating-the-window

        See also: https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-createwindoww

        :return: window hwnd
        """
        wc = win32gui.WNDCLASS()
        wc.lpfnWndProc = self._on_message
        wc.lpszClassName = self.__class__.__name__
        wc.hInstance = win32api.GetModuleHandle(None)
        class_atom = win32gui.RegisterClass(wc)
        return win32gui.CreateWindow(class_atom, self.__class__.__name__, 0, 0, 0, 0, 0, 0, 0, wc.hInstance, None)

    def start(self):
        hwnd = self._create_window()
        print(f'Created listener window with hwnd={hwnd:x}')
        print(f'Listening to messages')
        win32gui.PumpMessages()

    def _on_message(self, hwnd: int, msg: int, wparam: int, lparam: int):
        if msg != win32con.WM_DEVICECHANGE:
            return 0
        event, description = self.WM_DEVICECHANGE_EVENTS[wparam]
        print(f'Received message: {event} = {description}')
        if event in ('DBT_DEVNODES_CHANGED'):
            self.on_change()
        return 0

    def mouseEvent(self, event):
        mouse.unhook_all()
        if self.waitForMouseMovement:
            self.waitForMouseMovement = False
            self.sendBatteryLevelRequest()

    def sendBatteryLevelRequest(self):
        if self.isConnected:
            print("checking battery level...")
            self.send_device.close()
            self.recv_device.close()
            self.send_device.open()
            self.recv_device.open()
            # set received data handler
            self.recv_device.set_raw_data_handler(self.battery_level_handler)

            # find target usage
            for report in self.send_device.find_output_reports() + self.send_device.find_feature_reports():
                if self.target_usage in report:
                    # set target usage message
                    report[self.target_usage] = self.request_battery_level_message
                    # validate that message was set
                    new_raw_data = report.get_raw_data()
                    print("Set raw report: {0}\n".format(new_raw_data))
                    # send battery level request
                    report.set_raw_data(new_raw_data)
                    report.send()
                    print("Report sent")
            # putting send_device and recv_device.close() into battery_level_handler throws some obscure error for some reason
            # while not self.received: pass
            # self.received = False
            # self.send_device.close()
            # self.recv_device.close()
        else:
            print("device is disconnected, skipping battery level check")

    def on_change(self):
        # find target device
        self.wireless_hids = hid.HidDeviceFilter(vendor_id = self.vendor_id, product_id = self.product_id_wireless).get_devices()
        self.wired_hids = hid.HidDeviceFilter(vendor_id = self.vendor_id, product_id = self.product_id_wired).get_devices()
        self.target_usage = hid.get_full_usage_id(0xff02, 0x02)
        # if found
        if self.wireless_hids or self.wired_hids:
            if hasattr(self, "hid"): lastmode = "wired" if self.hid[0].product_id == self.product_id_wired else "wireless"
            if self.wired_hids:
                if hasattr(self, "hid") and lastmode == "wireless": self.isConnected = False
                self.hid = self.wired_hids
                self.myicon.icon = Image.open(fr"{self.dir_path}\\wired.png")
                print("wired mode")
            elif self.wireless_hids:
                if hasattr(self, "hid") and lastmode == "wired": self.isConnected = False
                self.hid = self.wireless_hids
                self.myicon.icon = Image.open(fr"{self.dir_path}\\wireless.png")
                print("wireless mode")
            if not self.isConnected:
                self.isConnected = True
                print("device (re)connected/changed mode, (re)defining objects...")
                # search for send and receive device
                searchString = "hid#vid_" + str(hex(self.vendor_id))[2:] + "&pid_" + str(hex(self.hid[0].product_id))[2:] + "&mi_01&col"
                for index, device in enumerate(self.hid):
                    if searchString + "07" in device.device_path:
                        self.send_device = self.hid[index]
                    if searchString + "05" in device.device_path:
                        self.recv_device = self.hid[index]
                self.sendBatteryLevelRequest()
                self.nextTimer.cancel()
                self.nextTimer = threading.Timer(self.checkEvery, self.timerChecker)
                self.nextTimer.start()
            else:
                print("false event received, device was not disconnected")
        else:
            self.nextTimer.cancel()
            print("device disconnected")
            self.isConnected = False
            self.myicon.icon = Image.open(fr"{self.dir_path}\\disconnected.png")

    def battery_level_handler(self, data):
        print("Raw data: {0}".format(data))
        print(f"Battery level: {data[6]*10}%")
        if data[6] == 0:
            self.myicon.icon = Image.open(fr"{self.dir_path}\\mousenotresponding.png")
            print("Mouse battery reported as 0% because mouse was never moved after dongle was connected.")
            self.waitForMouseMovement = True
            mouse.hook(self.mouseEvent)
        else:
            mode = "wired" if self.hid[0].product_id == self.product_id_wired else "wireless"
            self.myicon.icon = Image.open(fr"{self.dir_path}\\{mode}.png")
            wrg.SetValueEx(self.charge, "Value", 0, wrg.REG_SZ, str(data[6]))
        # self.received = True
        self.send_device.close()
        # workaround to stop recv_device from joining input processing
        # thread and throwing error (pywinusb.hid.core line 645)
        self.recv_device._HidDevice__input_processing_thread = None
        self.recv_device.close()

    def timerChecker(self):
        self.nextTimer.cancel()
        self.nextTimer = threading.Timer(self.checkEvery, self.timerChecker)
        self.nextTimer.start()
        print("running scheduled battery check...")
        self.sendBatteryLevelRequest()

    def kill(self):
        self.nextTimer.cancel()
        self.myicon.visible = False
        self.myicon.stop()
        wrg.SetValueEx(self.charge, "Value", 0, wrg.REG_SZ, "0")
        os._exit(0)

if __name__ == '__main__':
    listener = DeviceListener(vid, pid_wired, pid_wireless, checkEvery)
    listener.start()
