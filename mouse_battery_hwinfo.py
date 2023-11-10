# https://abdus.dev/posts/python-monitor-usb/
import win32api, win32con, win32gui
import pywinusb.hid as hid
from PIL import Image
from pystray import Icon as icon, Menu as menu, MenuItem as item
import winreg as wrg
import threading
import os

# VID and PID is for Zet Gaming Prime Pro Wireless V2 (PAW3370)
# (pretty sure just a OEM Pwnage Ultra Custom Wireless Symm 1 Gen 2)
vid = 0x25a7
pid = 0xfa59

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

    def __init__(self, vendor_id, product_id, checkEvery):
        self.checkEvery = checkEvery
        self.isConnected = False
        self.request_battery_level_message = [0x04, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x49]
        self.received = False
        self.dir_path = os.path.dirname(os.path.realpath(__file__))
        self.hwinfo = wrg.CreateKeyEx(wrg.HKEY_CURRENT_USER, r"SOFTWARE\\HWiNFO64\\Sensors\\Custom")
        self.mouse = wrg.CreateKeyEx(self.hwinfo, r"Mouse")
        self.charge = wrg.CreateKeyEx(self.mouse, r"Other0")
        wrg.SetValueEx(self.charge, "Name", 0, wrg.REG_SZ, "Mouse battery")
        wrg.SetValueEx(self.charge, "Value", 0, wrg.REG_SZ, "0")
        wrg.SetValueEx(self.charge, "Unit", 0, wrg.REG_SZ, "/10")

        self.myicon = icon('Mouse battery', Image.open(fr"{self.dir_path}\\mouse.png"), menu=menu(
            item("Exit", self.kill, default=True)
        ))

        self.myicon.run_detached()
        self.on_change()
        self.timerChecker()

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
        print(f'Listening to drive changes')
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
            while not self.received: pass
            self.received = False
            self.send_device.close()
            self.recv_device.close()
        else:
            print("device is disconnected, skipping battery level check")

    def on_change(self):
        # find target device
        self.all_hids = hid.HidDeviceFilter(vendor_id = vid, product_id = pid).get_devices()
        self.target_usage = hid.get_full_usage_id(0xff02, 0x02)
        # if found
        if self.all_hids:
            if not self.isConnected:
                print("device reconnected, redefining objects...")
                # search for send and receive device
                for index, device in enumerate(self.all_hids):
                    if "hid#vid_25a7&pid_fa59&mi_01&col07" in device.device_path:
                        self.send_device = self.all_hids[index]
                    if "hid#vid_25a7&pid_fa59&mi_01&col05" in device.device_path:
                        self.recv_device = self.all_hids[index]
            else:
                print("false alarm, device still connected")
            self.isConnected = True
        else:
            print("device disconnected")
            self.isConnected = False
            self.myicon.icon = Image.open(fr"{self.dir_path}\\Disconnected.png")

    def battery_level_handler(self, data):
        print("Raw data: {0}".format(data))
        print(f"Battery level: {data[6]*10}%")
        if data[6] == 0:
            self.myicon.icon = Image.open(fr"{self.dir_path}\\MouseNotResponding.png")
            print("Mouse battery reported as 0% because mouse was never moved after dongle was connected.")
        else:
            self.myicon.icon = Image.open(fr"{self.dir_path}\\mouse.png")
            wrg.SetValueEx(self.charge, "Value", 0, wrg.REG_SZ, str(data[6]))
        self.received = True
        return

    def timerChecker(self):
        self.nextTimer = threading.Timer(self.checkEvery, self.timerChecker)
        self.nextTimer.start()
        print("running scheduled battery check...")
        self.sendBatteryLevelRequest()

    def kill(self):
        self.nextTimer.cancel()
        self.myicon.stop()
        wrg.SetValueEx(self.charge, "Value", 0, wrg.REG_SZ, "0")
        os._exit(0)

if __name__ == '__main__':
    listener = DeviceListener(vid, pid, checkEvery)
    listener.start()
