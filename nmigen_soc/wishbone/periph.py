from nmigen import *

from .bus import *

import ..csr
from ..csr.periph import Bank as CSRBank, EventSource, InterruptSource
from ..csr.wishbone import WishboneCSRBridge


__all__ = ["Peripheral", "PeripheralBridge"]


class Peripheral:
    """TODO
    """
    def __init__(self):
        self._csr_banks = []
        self._triggers  = []

        self._bus       = None
        self._irq       = None

    @property
    def bus(self):
        if self._bus is None:
            raise NotImplementedError("Peripheral {!r} does not have a bus interface"
                                      .format(self))
        return self._bus

    @bus.setter
    def bus(self, bus):
        if not isinstance(bus, Interface):
            raise TypeError("Bus interface must be an instance of wishbone.Interface, not {!r}"
                            .format(bus))
        self._bus = bus

    @property
    def irq(self):
        if self._irq is None:
            raise NotImplementedError("Peripheral {!r} does not have an IRQ line"
                                      .format(self))
        return self._irq

    @irq.setter
    def irq(self, irq):
        if not isinstance(irq, Signal):
            raise TypeError("IRQ line must be a Signal, not {!r}"
                            .format(irq))
        # TODO check width, signed
        self._irq = irq

    def csr_bank(self, *, addr=None, alignment=0):
        bank = CSRBank(data_width=8, alignment=alignment)
        self._csr_banks.append((bank, addr, alignment))
        return bank

    def window(self, *, addr_width, data_width, granularity=None, features=frozenset(),
               addr=None, sparse=None):
        window = Interface(addr_width=addr_width, data_width=width, granularity=granularity,
                           features=features, src_loc_at=1)
        self._windows.append((window, addr, sparse))
        return window

    def trigger(self, *, mode="level"):
        trigger = Signal(src_loc_at=1)
        event   = csr.EventSource(mode=mode)
        self._triggers.append((trigger, event))
        return trigger

    def bridge(self, *, data_width=8, granularity=None, features=frozenset()):
        return PeripheralBridge(self, data_width=data_width, granularity=granularity,
                                features=features)

    def iter_csr_banks(self):
        for bank, addr, alignment in self._csr_banks:
            yield bank, addr, alignment

    def iter_windows(self):
        for window, addr, sparse in self._windows:
            yield window, addr, sparse

    def iter_triggers(self):
        for trigger, event in self._triggers:
            yield trigger, event


class PeripheralBridge(Elaboratable):
    """Peripheral bridge.

    TODO
    """
    def __init__(self, target, *, data_width, granularity, features):
        assert isinstance(target, Peripheral)

        # FIXME hardcoded CSR mux data_width

        self._wb_decoder = Decoder(addr_width=1, data_width=data_width, granularity=granularity,
                                   features=features)
        self._csr_subs   = []

        for bank, bank_addr, bank_alignment in target.iter_csr_banks():
            csr_mux    = csr.Multiplexer(addr_width=1, data_width=8, alignment=bank_alignment)
            for elem, elem_addr, elem_alignment in bank.iter_csrs():
                csr_mux.add(elem, addr=elem_addr, alignment=elem_alignment, extend=True)
            csr_bridge = WishboneCSRBridge(csr_mux.bus, data_width=bus_data_width)
            self._csr_subs.append((csr_mux, csr_bridge))

            self._wb_decoder.align_to(bank_alignment)
            self._wb_decoder.add(csr_bridge.wb_bus, addr=bank_addr, extend=True)

        for window, window_addr, window_sparse in target.iter_windows():
            self._wb_decoder.add(window, addr=window_addr, sparse=window_sparse, extend=True)

        triggers = list(target.iter_triggers())
        if len(triggers) > 0:
            self._int_source = csr.InterruptSource(triggers)
            self._int_bridge = WishboneCSRBridge(int_source.csr_bus, data_width=bus_data_width)
            self._wb_decoder.add(self._int_bridge, extend=True)
        else:
            self._int_source = None
            self._int_bridge = None

        self.bus = self._wb_decoder.bus
        self.irq = Signal()

    def elaborate(self, platform):
        m = Module()

        for i, (csr_mux, csr_bridge) in enumerate(self._csr_subs):
            m.submodules[   "csr_mux_{}".format(i)] = csr_mux
            m.submodules["csr_bridge_{}".format(i)] = csr_bridge

        if self._int_source is not None:
            m.submodules.int_source = self._int_source
            m.submodules.int_bridge = self._int_bridge
            m.d.comb += self.irq.eq(self._int_source.irq)
        else:
            m.d.comb += self.irq.eq(Const(0))

        m.submodules.wb_decoder = self._wb_decoder

        return m
