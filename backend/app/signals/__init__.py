"""Signal output: from the controller's lamp decisions to signal hardware, behind an independent safety monitor.

  controller.lamps()  ->  SignalOutput.apply()  ->  ConflictMonitor (independent checks)  ->  SignalDriver
                                                         | any violation
                                                         v
                                              latched FLASH (all-red flashing) until an operator reset

See monitor.py (the checks), drivers.py (none / simulated field controller; how to add a hardware driver) and
output.py (wiring, fault latch, reset)."""
from .drivers import DRIVERS, NullDriver, SignalDriver, SimulatedController, create_driver
from .monitor import ConflictMonitor, Fault, MonitorConfig
from .output import SignalOutput

__all__ = ["DRIVERS", "ConflictMonitor", "Fault", "MonitorConfig", "NullDriver", "SignalDriver", "SignalOutput",
           "SimulatedController", "create_driver"]
