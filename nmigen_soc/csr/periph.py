from nmigen import *

from .bus import *


__all__ = ["Peripheral", "PeripheralBridge", "EventSource", "InterruptSource", "Bank"]


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
        if not isinstance(bus, csr.Interface):
            raise TypeError("Bus interface must be an instance of csr.Interface, not {!r}"
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
        bank = Bank(data_width=8, alignment=alignment)
        self._csr_banks.append((bank, addr, alignment))
        return bank

    def trigger(self, *, mode="level"):
        trigger = Signal(src_loc_at=1)
        event   = EventSource(mode=mode)
        self._triggers.append((trigger, event))
        return trigger

    def bridge(self, *, data_width=8):
        return PeripheralBridge(self, data_width=data_width)

    def iter_csr_banks(self):
        for bank, addr, alignment in self._csr_banks:
            yield bank, addr, alignment

    def iter_triggers(self):
        for trigger, event in self._triggers:
            yield trigger, event


class Bank:
    def __init__(self):
        self._csrs = []

    def csr(self, width, access, *, addr=None, alignment=None, name=None):
        elem = csr.Element(width, access, name=name, src_loc_at=1)
        self._csrs.append(elem, addr, alignment)
        return elem

    def iter_csrs(self):
        for elem, addr, alignment in self._csrs:
            yield elem, addr, alignment


class PeripheralBridge(Elaboratable):
    def __init__(self, target, *, data_width):
        assert isinstance(target, Peripheral)

        self._decoder = Decoder(addr_width=1, data_width=data_width)
        self._muxes   = []

        for bank, bank_addr, bank_alignment in target.iter_csr_banks():
            mux = Multiplexer(addr_width=1, data_width=data_width, alignment=bank_alignment)
            for elem, elem_addr, elem_alignment in bank.iter_csrs():
                mux.add(elem, addr=elem_addr, alignment=elem_alignment, extend=True)
            self._muxes.append(mux)

            self._decoder.align_to(bank_alignment)
            self._decoder.add(mux.bus, addr=bank_addr, extend=True)

        triggers = list(target.iter_triggers())
        if len(triggers) > 0:
            self._int_source = InterruptSource(triggers, data_width=data_width)
            self._decoder.add(self._int_source.bus, extend=True)
        else:
            self._int_source = None

        self.bus = self._decoder.bus
        self.irq = Signal()

    def elaborate(self, platform):
        m = Module()

        for i, mux in enumerate(self._muxes):
            m.submodules["mux_{}".format(i)] = mux

        if self._int_source is not None:
            m.submodules.int_source = self._int_source
            m.d.comb += self.irq.eq(self._int_source.irq)
        else:
            m.d.comb += self.irq.eq(Const(0))

        m.submodules.decoder = self._decoder

        return m


class EventSource(Elaboratable):
    """TODO
    """
    def __init__(self, *, mode):
        choices = ("level", "rise", "fall")
        if mode not in choices:
            raise ValueError("Invalid trigger mode {!r}; must be one of {}"
                             .format(mode, ", ".join(choices)))
        self.mode    = mode

        self.trigger = Signal()
        self.en      = Signal()

    def elaborate(self, platform):
        m = Module()

        if self.mode in ("rise", "fall"):
            trigger_r = Signal.like(self.trigger, name_suffix="_r")
            m.d.sync += trigger_r.eq(self.trigger)

        if self.mode == "level":
            m.d.comb += self.en.eq(self.trigger)
        if self.mode == "rise":
            m.d.comb += self.en.eq(~trigger_r &  self.trigger)
        if self.mode == "fall":
            m.d.comb += self.en.eq( trigger_r & ~self.trigger)

        return m


class InterruptSource(Elaboratable):
    """TODO
    """
    def __init__(self, sources, *, data_width):
        for source in sources:
            assert isinstance(source, EventSource)
        self._sources = list(sources)

        self._status  = Element(len(self._sources), "r")
        self._pending = Element(len(self._sources), "rw")
        self._enable  = Element(len(self._sources), "rw")

        self._mux = Multiplexer(addr_width=1, data_width=data_width)
        self._mux.add(self._status,  extend=True)
        self._mux.add(self._pending, extend=True)
        self._mux.add(self._enable,  extend=True)

        self.bus  = self._mux.bus
        self.irq  = Signal()

    def elaborate(self, platform):
        m = Module()
        m.submodules.mux = self._mux

        with m.If(self._pending.w_stb):
            m.d.sync += self._pending.r_data.eq(self._pending.r_data & ~self._pending.w_data)

        for i, (trigger, event) in enumerate(self._sources):
            m.submodules["event_{}".format(trigger.name)] = event
            m.d.comb += event.trigger.eq(trigger)
            m.d.sync += self._status.r_data[i].eq(event.en)
            with m.If(event.en):
                m.d.sync += self._pending.r_data[i].eq(1)

        with m.If(self._enable.w_stb):
            m.d.sync += self._enable.r_data.eq(self._enable.w_data)

        m.d.comb += self.irq.eq((self._pending.r_data & self._enable.r_data).any())

        return m
