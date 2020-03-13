from nmigen import *

from .bus import *


__all__ = ["Peripheral", "PeripheralBridge"]
# __all__ = ["Peripheral", "Bank", "PeripheralBridge", "EventSource", "InterruptSource"]


# def _check_trigger_mode(mode):
#     choices = ("level", "rise", "fall")
#     if mode not in choices:
#         raise ValueError("Invalid trigger mode {!r}; must be one of {}"
#                          .format(mode, ", ".join(choices)))


class Peripheral:
    """TODO
    """
    def __init__(self):
        self._csrs    = []
        self._csr_bus = None

        # self._triggers = []
        # self._irq  = None

    @property
    def csr_bus(self):
        if self._csr_bus is None:
            raise NotImplementedError("Peripheral {!r} does not have a CSR bus interface"
                                      .format(self))
        return self._csr_bus

    @csr_bus.setter
    def csr_bus(self, csr_bus):
        if not isinstance(csr_bus, Interface):
            raise TypeError("CSR bus interface must be an instance of csr.Interface, not {!r}"
                            .format(csr_bus))
        self._csr_bus = csr_bus

    # @property
    # def irq(self):
    #     if self._irq is None:
    #         raise NotImplementedError("Peripheral {!r} does not have an IRQ line"
    #                                   .format(self))
    #     return self._irq

    # @irq.setter
    # def irq(self, irq):
    #     if not isinstance(irq, Signal) or irq.shape() != Shape(1, signed=False):
    #         raise TypeError("IRQ line must be a 1-bit wide unsigned Signal, not {!r}"
    #                         .format(irq))
    #     self._irq = irq

    def csr(self, width, access, *, addr=None, alignment=0, name=None):
        elem = Element(width, access, name=name, src_loc_at=1)
        self._csrs.append((elem, addr, alignment))
        return elem

    # def trigger(self, *, mode="level"):
    #     _check_trigger_mode(mode)
    #     trigger = Signal(src_loc_at=1)
    #     self._triggers.append((trigger, mode))
    #     return trigger

    def csr_bridge(self, *, data_width=8, alignment=0):
        return PeripheralBridge(self, data_width=data_width, alignment=alignment)

    def iter_csrs(self):
        for elem, addr, alignment in self._csrs:
            yield elem, addr, alignment

    # def iter_triggers(self):
    #     for trigger, mode in self._triggers:
    #         yield trigger, mode


class PeripheralBridge(Elaboratable):
    def __init__(self, target, *, data_width, alignment):
        self._mux = Multiplexer(addr_width=1, data_width=data_width, alignment=alignment)

        for elem, elem_addr, elem_alignment in target.iter_csrs():
            self._mux.add(elem, addr=elem_addr, alignment=elem_alignment, extend=True)

        self.bus  = self._mux.bus

        # events = []
        # for trigger, mode in target.iter_triggers():
        #     events.append((EventSource(mode=mode), trigger))

        # if len(events) > 0:
        #     self._int_source = InterruptSource(events, data_width=data_width)
        #     self._decoder.add(self._int_source.bus, extend=True)
        # else:
        #     self._int_source = None

    def elaborate(self, platform):
        m = Module()

        # if self._int_source is not None:
        #     m.submodules.int_source = self._int_source
        #     m.d.comb += self.irq.eq(self._int_source.irq)
        # else:
        #     m.d.comb += self.irq.eq(Const(0))

        m.submodules.mux = self._mux

        return m


# class EventSource(Elaboratable):
#     """TODO
#     """
#     def __init__(self, *, mode):
#         _check_trigger_mode(mode)
#         self.mode    = mode

#         self.trigger = Signal()
#         self.en      = Signal()

#     def elaborate(self, platform):
#         m = Module()

#         if self.mode in ("rise", "fall"):
#             trigger_r = Signal.like(self.trigger, name_suffix="_r")
#             m.d.sync += trigger_r.eq(self.trigger)

#         if self.mode == "level":
#             m.d.comb += self.en.eq(self.trigger)
#         if self.mode == "rise":
#             m.d.comb += self.en.eq(~trigger_r &  self.trigger)
#         if self.mode == "fall":
#             m.d.comb += self.en.eq( trigger_r & ~self.trigger)

#         return m


# class InterruptSource(Elaboratable):
#     """TODO
#     """
#     def __init__(self, events, *, data_width):
#         self._events  = list(events)

#         self._status  = Element(len(self._events), "r")
#         self._pending = Element(len(self._events), "rw")
#         self._enable  = Element(len(self._events), "rw")

#         self._mux = Multiplexer(addr_width=1, data_width=data_width)
#         self._mux.add(self._status,  extend=True)
#         self._mux.add(self._pending, extend=True)
#         self._mux.add(self._enable,  extend=True)

#         self.bus  = self._mux.bus
#         self.irq  = Signal()

#     def elaborate(self, platform):
#         m = Module()
#         m.submodules.mux = self._mux

#         with m.If(self._pending.w_stb):
#             m.d.sync += self._pending.r_data.eq(self._pending.r_data & ~self._pending.w_data)

#         for i, (event, trigger) in enumerate(self._events):
#             m.submodules["event_{}".format(trigger.name)] = event
#             m.d.comb += event.trigger.eq(trigger)
#             m.d.sync += self._status.r_data[i].eq(event.en)
#             with m.If(event.en):
#                 m.d.sync += self._pending.r_data[i].eq(1)

#         with m.If(self._enable.w_stb):
#             m.d.sync += self._enable.r_data.eq(self._enable.w_data)

#         m.d.comb += self.irq.eq((self._pending.r_data & self._enable.r_data).any())

#         return m
