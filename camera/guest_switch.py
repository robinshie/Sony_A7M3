"""Run in the dedicated Alpine VM with Sony-PMCA-RE and PyUSB installed."""
import sys
from pmca.usb import MscDevice
from pmca.usb.driver.generic.libusb import MscContext
from pmca.usb.sony import (SonyExtCmdCamera, SonyMscExtCmdDevice, SonySenserAuthDevice,
                          isSonyMscCamera)

ctx = MscContext()
if sys.argv[1:] not in ([], ['--host-identity-check']):
    raise SystemExit('Unexpected guest-switch arguments.')
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
if not sys.argv[1:] and SonyExtCmdCamera(SonyMscExtCmdDevice(driver)).getCameraInfo().modelName != "ILCE-7M3":
    raise SystemExit("Unexpected Sony model.")
# The optional transport-only path is for callers that independently verify
# the maintenance model + build before executing any camera-side payload.
auth = SonySenserAuthDevice(driver)
auth.start()
auth.authenticate()
print("SONY_SERVICE_SWITCH_ACK", flush=True)
