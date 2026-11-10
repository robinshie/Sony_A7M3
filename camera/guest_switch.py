"""Run in the dedicated Alpine VM with Sony-PMCA-RE and PyUSB installed."""
from pmca.usb import MscDevice
from pmca.usb.driver.generic.libusb import MscContext
from pmca.usb.sony import (SonyExtCmdCamera, SonyMscExtCmdDevice, SonySenserAuthDevice,
                          isSonyMscCamera)

ctx = MscContext()
targets = [item for item in ctx.listDevices(0x054c) if item.idProduct == 0x0c02]
if len(targets) != 1:
    raise SystemExit("Expected exactly one Sony A7 III in mass-storage mode.")
driver = ctx.openDevice(targets[0])
driver.reset()
driver.backend.classInterfaceRequestOut(0xff, 0, 0)
for endpoint in driver.epIn + driver.epOut:
    driver.backend.clearHalt(endpoint)
if not isSonyMscCamera(MscDevice(driver).getDeviceInfo()):
    raise SystemExit("SCSI INQUIRY did not identify a Sony camera.")
if SonyExtCmdCamera(SonyMscExtCmdDevice(driver)).getCameraInfo().modelName != "ILCE-7M3":
    raise SystemExit("Unexpected Sony model.")
auth = SonySenserAuthDevice(driver)
auth.start()
auth.authenticate()
print("SONY_SERVICE_SWITCH_ACK", flush=True)
