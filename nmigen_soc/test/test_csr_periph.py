# nmigen: UnusedElaboratable=no

import unittest
from nmigen import *
from nmigen.back.pysim import *

from ..csr.bus import *
from ..csr.periph import *


class PeripheralTestCase(unittest.TestCase):
    def test_set_csr_bus_wrong(self):
        periph = Peripheral()
        with self.assertRaisesRegex(TypeError,
                r"CSR bus interface must be an instance of csr.Interface, not 'foo'"):
            periph.csr_bus = "foo"

    def test_get_csr_bus_wrong(self):
        periph = Peripheral()
        with self.assertRaisesRegex(NotImplementedError,
                r"Peripheral <.*> does not have a CSR bus interface"):
            periph.csr_bus

    # def test_set_irq_wrong(self):
    #     periph = Peripheral()
    #     with self.assertRaisesRegex(TypeError,
    #             r"IRQ line must be a 1-bit wide unsigned Signal, not 'foo'"):
    #         periph.irq = "foo"

    # def test_get_irq_wrong(self):
    #     periph = Peripheral():
    #     with self.assertRaisesRegex(NotImplementedError,
    #             r"Peripheral <*> does not have an IRQ line"):
    #         periph.irq

    def test_iter_csrs(self):
        periph = Peripheral()
        csr_0  = periph.csr(1, "r")
        csr_1  = periph.csr(8, "rw", addr=0x4, alignment=2)
        self.assertEqual((csr_0.width, csr_0.access), (1, Element.Access.R))
        self.assertEqual((csr_1.width, csr_1.access), (8, Element.Access.RW))
        self.assertEqual(list(periph.iter_csrs()), [
            (csr_0, None, 0),
            (csr_1,  0x4, 2),
        ])

    # def test_iter_triggers(self):
    #     periph = Peripheral()
    #     trig_0 = periph.trigger()
    #     trig_1 = periph.trigger(mode="rise")
    #     self.assertEqual(list(periph.iter_triggers()), [
    #         (trig_0, "level"),
    #         (trig_1, "rise"),
    #     ])


class PeripheralSimulationTestCase(unittest.TestCase):
    def test_simple(self):
        class DummyPeripheral(Peripheral, Elaboratable):
            def __init__(self):
                super().__init__()
                self.csr_0   = self.csr(8, "r")
                self.csr_1   = self.csr(8, "r", addr=8, alignment=4)
                self.csr_2   = self.csr(8, "w")
                self._bridge = self.csr_bridge(data_width=8, alignment=0)
                self.csr_bus = self._bridge.bus

            def elaborate(self, platform):
                m = Module()
                m.submodules.bridge = self._bridge
                return m

        dut = DummyPeripheral()

        def sim_test():
            yield dut.csr_0.r_data.eq(0xa)
            yield dut.csr_1.r_data.eq(0xb)

            yield dut.csr_bus.addr.eq(0)
            yield dut.csr_bus.r_stb.eq(1)
            yield
            yield dut.csr_bus.r_stb.eq(0)
            self.assertEqual((yield dut.csr_0.r_stb), 1)
            yield
            self.assertEqual((yield dut.csr_bus.r_data), 0xa)

            yield dut.csr_bus.addr.eq(8)
            yield dut.csr_bus.r_stb.eq(1)
            yield
            yield dut.csr_bus.r_stb.eq(0)
            self.assertEqual((yield dut.csr_1.r_stb), 1)
            yield
            self.assertEqual((yield dut.csr_bus.r_data), 0xb)

            yield dut.csr_bus.addr.eq(24)
            yield dut.csr_bus.w_stb.eq(1)
            yield dut.csr_bus.w_data.eq(0xc)
            yield
            yield dut.csr_bus.w_stb.eq(0)
            yield
            self.assertEqual((yield dut.csr_2.w_stb), 1)
            self.assertEqual((yield dut.csr_2.w_data), 0xc)

        with Simulator(dut, vcd_file=open("test.vcd", "w")) as sim:
            sim.add_clock(1e-6)
            sim.add_sync_process(sim_test())
            sim.run()
