# gamepad.py
__version__ = "4.0.0"

def get_version():
    return __version__
# CustomGamepad class for BGG Firmware
import usb_hid

class CustomGamepad:
    def __init__(self):
        for dev in usb_hid.devices:
            if dev.usage_page == 0x01 and dev.usage == 0x05:
                self.device = dev
                break
        else:
            raise RuntimeError("Custom HID gamepad not found")
        self.buttons = 0
        self.hat = 0x0F
        self.z_axis = 0

    def press(self, n):
        self.buttons |= (1 << (n - 1))
        self.send()
    def release(self, n):
        self.buttons &= ~(1 << (n - 1))
        self.send()
    def set_hat(self, d):
        self.hat = d & 0x0F
        self.send()
    def set_whammy(self, v):
        self.z_axis = max(0, min(255, v))
        self.send()
    def send(self):
        report = bytearray([
            self.buttons & 0xFF,
            (self.buttons >> 8) & 0x07,
            (self.hat & 0x0F) | 0xF0,
            self.z_axis
        ])
        try:
            self.device.send_report(report)
        except OSError:
            pass

