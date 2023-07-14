# amaranth: UnusedElaboratable=no

import unittest
from amaranth import *
from amaranth.lib import data
from amaranth.sim import *

from amaranth_soc import csr


class GenericFieldTestCase(unittest.TestCase):
    class MockField(csr.GenericField):
        def intr_read(self, storage):
            return storage

        def intr_write(self, storage, w_data):
            return storage ^ w_data

        def user_write(self, storage, w_data):
            return storage ^ w_data

    def test_simple(self):
        field = self.MockField(unsigned(4), reset=0xa)
        self.assertEqual(field.shape, unsigned(4))
        self.assertEqual(field.reset, 0xa)
        self.assertEqual(field.intr_read(0x5), 0x5)
        self.assertEqual(field.intr_write(0x5, 0xa), 0xf)
        self.assertEqual(field.user_write(0x5, 0xa), 0xf)

    def test_reset_default(self):
        field = self.MockField(1)
        self.assertEqual(field.reset, 0)

    def test_eq(self):
        self.assertEqual(self.MockField(4, reset=0xa), self.MockField(unsigned(4), reset=0xa))
        self.assertEqual(self.MockField(4, reset=0xa),
                         self.MockField(4, reset=Const(2, 2).replicate(2)))
        self.assertNotEqual(self.MockField(4, reset=0xa), csr.field.RW1C(4, reset=0xa))
        self.assertNotEqual(self.MockField(4, reset=0xa), self.MockField(8, reset=0xa))
        self.assertNotEqual(self.MockField(4, reset=0xa), self.MockField(4, reset=0x5))

    def test_wrong_shape(self):
        with self.assertRaisesRegex(TypeError,
                r"Field shape must be a shape-castable object, not 'foo'"):
            self.MockField("foo")

    def test_wrong_reset(self):
        with self.assertRaisesRegex(TypeError,
                r"Reset value must be a constant-castable expression, not 'foo'"):
            self.MockField(unsigned(1), reset="foo")


class FieldMapTestCase(unittest.TestCase):
    def test_simple(self):
        field_map = csr.FieldMap({
            "a": csr.field.R(unsigned(1)),
            "b": csr.field.RW(signed(3), reset=-1),
            "c": csr.FieldMap({
                "d": csr.field.RW1C(unsigned(4)),
            }),
        })
        self.assertEqual(field_map.size, 8)
        self.assertEqual(field_map.shape, data.StructLayout({
            "a": unsigned(1),
            "b": signed(3),
            "c": data.StructLayout({
                "d": unsigned(4),
            }),
        }))
        self.assertEqual(field_map.reset, {
            "a": 0,
            "b": -1,
            "c": {
                "d": 0,
            },
        })
        self.assertEqual(field_map["a"], csr.field.R(unsigned(1)))
        self.assertEqual(field_map["b"], csr.field.RW(signed(3), reset=-1))
        self.assertEqual(field_map["c"], csr.FieldMap({"d": csr.field.RW1C(unsigned(4))}))

    def test_iter(self):
        field_map = csr.FieldMap({
            "a": csr.field.R(unsigned(1)),
            "b": csr.field.RW(signed(3), reset=-1),
        })
        self.assertEqual(list(field_map), [
            ("a", csr.field.R(unsigned(1))),
            ("b", csr.field.RW(signed(3), reset=-1)),
        ])

    def test_eq(self):
        self.assertEqual(csr.FieldMap({"a": csr.field.R(1), "b": csr.field.W(2)}),
                         csr.FieldMap({"a": csr.field.R(1), "b": csr.field.W(2)}))
        self.assertNotEqual(csr.FieldMap({"a": csr.field.R(1), "b": csr.field.W(2)}),
                            csr.FieldMap({"a": csr.field.R(1)}))
        self.assertNotEqual(csr.FieldMap({"a": csr.field.R(1), "b": csr.field.W(2)}),
                            csr.FieldMap({"a": csr.field.W(2), "b": csr.field.R(1)}))
        self.assertNotEqual(csr.FieldMap({"a": csr.field.R(1), "b": csr.field.W(2)}),
                            csr.FieldMap({"b": csr.field.W(2), "a": csr.field.R(1)}))

    def test_iter_all_fields(self):
        field_map = csr.FieldMap({
            "a": csr.field.R(unsigned(1)),
            "b": csr.field.RW(signed(3), reset=-1),
            "c": csr.FieldMap({
                "d": csr.field.RW1C(unsigned(4)),
            }),
        })
        self.assertEqual(list(field_map.all_fields()), [
            (("a",), csr.field.R(unsigned(1))),
            (("b",), csr.field.RW(signed(3), reset=-1)),
            (("c", "d"), csr.field.RW1C(unsigned(4))),
        ])

    def test_wrong_mapping(self):
        with self.assertRaisesRegex(TypeError,
                r"Fields must be provided as a non-empty mapping, not 'foo'"):
            csr.FieldMap("foo")

    def test_wrong_field_key(self):
        with self.assertRaisesRegex(TypeError,
                r"Field name must be a non-empty string, not 1"):
            csr.FieldMap({1: csr.field.R(1)})
        with self.assertRaisesRegex(TypeError,
                r"Field name must be a non-empty string, not ''"):
            csr.FieldMap({"": csr.field.R(1)})

    def test_wrong_field_value(self):
        with self.assertRaisesRegex(TypeError,
                r"Field must be a GenericField or a FieldMap, not unsigned\(1\)"):
            csr.FieldMap({"a": unsigned(1)})

    def test_getitem_wrong_key(self):
        with self.assertRaises(KeyError):
            csr.FieldMap({"a": csr.field.R(1)})["b"]


class FieldArrayTestCase(unittest.TestCase):
    def test_simple(self):
        field_array = csr.FieldArray(csr.field.R(unsigned(2), reset=3), length=8)

        self.assertEqual(field_array.size, 16)
        self.assertEqual(field_array.shape, data.ArrayLayout(unsigned(2), 8))
        self.assertEqual(field_array.reset, dict(enumerate(3 for _ in range(8))))
        for i in range(8):
            self.assertEqual(field_array[i], csr.field.R(unsigned(2), reset=3))

    def test_dim_2(self):
        field_array = csr.FieldArray(csr.FieldArray(csr.field.R(unsigned(1), reset=1), length=4),
                                     length=4)

        self.assertEqual(field_array.size, 16)
        self.assertEqual(field_array.shape,
                         data.ArrayLayout(data.ArrayLayout(unsigned(1), length=4), length=4))
        self.assertEqual(field_array.reset,
                         dict(enumerate(dict(enumerate(1 for _ in range(4))) for _ in range(4))))
        for i in range(4):
            self.assertEqual(field_array[i],
                             csr.FieldArray(csr.field.R(1, reset=1), length=4))

    def test_nested(self):
        field_array = csr.FieldArray(
                csr.FieldMap({
                    "a": csr.field.R(unsigned(4), reset=0xa),
                    "b": csr.FieldArray(csr.field.R(unsigned(1)), length=4),
                }), length=4)

        self.assertEqual(field_array.size, 32)
        self.assertEqual(field_array.shape,
                         data.ArrayLayout(data.StructLayout({
                             "a": unsigned(4),
                             "b": data.ArrayLayout(unsigned(1), length=4),
                         }), length=4))
        self.assertEqual(field_array.reset,
                         dict(enumerate({"a": 0xa, "b": dict(enumerate(0 for _ in range(4)))}
                                        for _ in range(4))))
        for i in range(4):
            self.assertEqual(field_array[i], csr.FieldMap({
                "a": csr.field.R(unsigned(4), reset=0xa),
                "b": csr.FieldArray(csr.field.R(unsigned(1)), length=4),
            }))
            for j in range(4):
                self.assertEqual(field_array[i]["b"][j], csr.field.R(unsigned(1)))

    def test_iter(self):
        field_array = csr.FieldArray(csr.field.R(1), length=3)
        self.assertEqual(list(field_array), [
            (i, csr.field.R(1)) for i in range(3)
        ])

    def test_eq(self):
        self.assertEqual(csr.FieldArray(csr.field.R(1), length=4),
                         csr.FieldArray(csr.field.R(1), length=4))
        self.assertNotEqual(csr.FieldArray(csr.field.R(1), length=4),
                            csr.FieldArray(csr.field.W(1), length=4))
        self.assertNotEqual(csr.FieldArray(csr.field.R(1), length=4),
                            csr.FieldArray(csr.field.R(1), length=5))
        self.assertNotEqual(csr.FieldArray(csr.field.R(1), length=4),
                            csr.FieldArray(csr.field.R(4), length=1))

    def test_iter_all_fields(self):
        field_array = csr.FieldArray(
                csr.FieldMap({
                    "a": csr.field.R(4, reset=0xa),
                    "b": csr.FieldArray(csr.field.R(1), length=2),
                }), length=2)
        self.assertEqual(list(field_array.all_fields()), [
            ((0, "a"), csr.field.R(4, reset=0xa)),
            ((0, "b", 0), csr.field.R(1)),
            ((0, "b", 1), csr.field.R(1)),
            ((1, "a"), csr.field.R(4, reset=0xa)),
            ((1, "b", 0), csr.field.R(1)),
            ((1, "b", 1), csr.field.R(1)),
        ])

    def test_wrong_field(self):
        with self.assertRaisesRegex(TypeError,
                r"Field must be a GenericField or a FieldMap, not 'foo'"):
            csr.FieldArray("foo", 4)

    def test_wrong_length(self):
        with self.assertRaisesRegex(TypeError,
                r"Field array length must be a positive integer, not 'foo'"):
            csr.FieldArray(csr.field.R(1), "foo")
        with self.assertRaisesRegex(TypeError,
                r"Field array length must be a positive integer, not 0"):
            csr.FieldArray(csr.field.R(1), 0)

    def test_getitem_wrong_key(self):
        with self.assertRaisesRegex(TypeError,
                r"Cannot index field array with 'a'"):
            csr.FieldArray(csr.field.R(1), 1)["a"]
        with self.assertRaises(KeyError):
            csr.FieldArray(csr.field.R(1), 1)[1]
        with self.assertRaises(KeyError):
            csr.FieldArray(csr.field.R(1), 1)[-2]


class RegisterInterfaceTestCase(unittest.TestCase):
    class MockRegisterInterface(csr.RegisterInterface):
        a: csr.field.R(unsigned(1))
        b: csr.field.RW1C(unsigned(3))
        c: csr.FieldMap({"d": csr.field.RW(signed(2))})
        e: csr.FieldArray(csr.field.W(unsigned(1)), length=2)

        foo: unsigned(42)

    def test_simple(self):
        iface = csr.RegisterInterface(csr.FieldMap({
            "a": csr.field.R(unsigned(1)),
            "b": csr.field.RW1C(unsigned(3)),
        }))
        self.assertEqual(iface.field_map, csr.FieldMap({
            "a": csr.field.R(unsigned(1)),
            "b": csr.field.RW1C(unsigned(3)),
        }))
        self.assertEqual(iface.readable, True)
        self.assertEqual(iface.writable, True)
        self.assertEqual(Value.cast(iface.w_data).width, iface.field_map.size)
        self.assertEqual(Value.cast(iface.w_stb) .width, 1)
        self.assertEqual(Value.cast(iface.r_data).width, iface.field_map.size)
        self.assertEqual(Value.cast(iface.r_stb) .width, 1)

    def test_annotations(self):
        iface = self.MockRegisterInterface()
        self.assertEqual(iface.field_map, csr.FieldMap({
            "a": csr.field.R(unsigned(1)),
            "b": csr.field.RW1C(unsigned(3)),
            "c": csr.FieldMap({"d": csr.field.RW(signed(2))}),
            "e": csr.FieldArray(csr.field.W(unsigned(1)), length=2),
        }))
        self.assertEqual(iface.readable, True)
        self.assertEqual(iface.writable, True)
        self.assertEqual(Value.cast(iface.w_data).width, iface.field_map.size)
        self.assertEqual(Value.cast(iface.w_stb) .width, 1)
        self.assertEqual(Value.cast(iface.r_data).width, iface.field_map.size)
        self.assertEqual(Value.cast(iface.r_stb) .width, 1)

    def test_readonly(self):
        iface = csr.RegisterInterface(csr.FieldMap({"a": csr.field.R(1)}))
        self.assertEqual(iface.readable, True)
        self.assertEqual(iface.writable, False)

    def test_writeonly(self):
        iface = csr.RegisterInterface(csr.FieldMap({"a": csr.field.W(1)}))
        self.assertEqual(iface.readable, False)
        self.assertEqual(iface.writable, True)

    def test_field_map_over_annotations(self):
        iface = self.MockRegisterInterface(csr.FieldMap({
            "a": csr.field.R(1),
        }))
        self.assertEqual(iface.field_map, csr.FieldMap({
            "a": csr.field.R(1),
        }))
        self.assertEqual(iface.readable, True)
        self.assertEqual(iface.writable, False)
        self.assertEqual(Value.cast(iface.w_data).width, iface.field_map.size)
        self.assertEqual(Value.cast(iface.w_stb) .width, 1)
        self.assertEqual(Value.cast(iface.r_data).width, iface.field_map.size)
        self.assertEqual(Value.cast(iface.r_stb) .width, 1)

    def test_wrong_field_map(self):
        with self.assertRaisesRegex(TypeError,
                r"Field map must be a FieldMap, not 'foo'"):
            csr.RegisterInterface("foo")


class RegisterFieldPortTestCase(unittest.TestCase):
    def test_user_ro(self):
        field = csr.field.W(unsigned(8))
        port  = csr.Register.FieldPort(field, name="foo")
        self.assertEqual(port.field, field)
        self.assertEqual(port.name, "foo")
        self.assertEqual(Value.cast(port.r_data).width, 8)
        self.assertEqual(Value.cast(port.r_stb) .width, 1)
        self.assertEqual(port.r_data.name, "foo__r_data")
        self.assertEqual(port.r_stb .name, "foo__r_stb")
        self.assertFalse(hasattr(port, "w_mask"))
        self.assertFalse(hasattr(port, "w_data"))
        self.assertFalse(hasattr(port, "w_ack"))

    def test_user_rw(self):
        field = csr.field.R(unsigned(8))
        port  = csr.Register.FieldPort(field, name="bar")
        self.assertEqual(port.field, field)
        self.assertEqual(port.name, "bar")
        self.assertEqual(Value.cast(port.r_data).width, 8)
        self.assertEqual(Value.cast(port.r_stb ).width, 1)
        self.assertEqual(Value.cast(port.w_mask).width, 8)
        self.assertEqual(Value.cast(port.w_data).width, 8)
        self.assertEqual(Value.cast(port.w_ack ).width, 1)
        self.assertEqual(port.r_data.name, "bar__r_data")
        self.assertEqual(port.r_stb .name, "bar__r_stb")
        self.assertEqual(port.w_mask.name, "bar__w_mask")
        self.assertEqual(port.w_data.name, "bar__w_data")
        self.assertEqual(port.w_ack .name, "bar__w_ack")


class RegisterUserPortTestCase(unittest.TestCase):
    def test_simple(self):
        field_map = csr.FieldMap({
            "a": csr.field.R(1),
            "b": csr.FieldArray(csr.FieldMap({"c": csr.field.W(1)}), length=2),
        })
        port = csr.Register.UserPort(field_map)

        self.assertTrue(isinstance(port.a,      csr.Register.FieldPort))
        self.assertTrue(isinstance(port.b,      csr.Register.UserPort))
        self.assertTrue(isinstance(port.b[0],   csr.Register.UserPort))
        self.assertTrue(isinstance(port.b[1],   csr.Register.UserPort))
        self.assertTrue(isinstance(port.b[0].c, csr.Register.FieldPort))
        self.assertTrue(isinstance(port.b[1].c, csr.Register.FieldPort))

        self.assertIs(port["a"],         port.a)
        self.assertIs(port["b"],         port.b)
        self.assertIs(port["b"][0]["c"], port.b[0].c)
        self.assertIs(port["b"][1]["c"], port.b[1].c)

        self.assertEqual(port.a     .field, csr.field.R(1))
        self.assertEqual(port.b[0].c.field, csr.field.W(1))
        self.assertEqual(port.b[1].c.field, csr.field.W(1))

        self.assertEqual(port.a     .name, "a")
        self.assertEqual(port.b[0].c.name, "b__n0__c")
        self.assertEqual(port.b[1].c.name, "b__n1__c")


class RegisterTestCase(unittest.TestCase):
    def test_simple(self):
        reg = csr.Register(csr.FieldMap({
            "a": csr.field.R(unsigned(1)),
            "b": csr.field.RW1C(unsigned(3)),
            "c": csr.FieldMap({"d": csr.field.RW(signed(2))}),
            "e": csr.FieldArray(csr.field.W(unsigned(1)), length=2),
        }))

        self.assertEqual(reg.f.a   .field, csr.field.R(unsigned(1)))
        self.assertEqual(reg.f.b   .field, csr.field.RW1C(unsigned(3)))
        self.assertEqual(reg.f.c.d .field, csr.field.RW(signed(2)))
        self.assertEqual(reg.f.e[0].field, csr.field.W(unsigned(1)))
        self.assertEqual(reg.f.e[1].field, csr.field.W(unsigned(1)))

    def test_sim(self):
        dut = csr.Register(csr.FieldMap({
            "a": csr.field.R(unsigned(1)),
            "b": csr.field.RW1C(unsigned(3), reset=0b111),
            "c": csr.FieldMap({"d": csr.field.RW(signed(2), reset=-1)}),
            "e": csr.FieldArray(csr.field.W(unsigned(1), reset=1), length=2),
            "f": csr.field.RW1S(unsigned(3)),
        }))

        def process():
            # Check reset values:

            self.assertEqual((yield dut.r_data.a),    0)
            self.assertEqual((yield dut.r_data.b),    0b111)
            self.assertEqual((yield dut.r_data.c.d), -1)
            self.assertEqual((yield dut.r_data.f),    0b000)

            self.assertEqual((yield dut.f.a   .r_data),  0)
            self.assertEqual((yield dut.f.b   .r_data),  0b111)
            self.assertEqual((yield dut.f.c.d .r_data), -1)
            self.assertEqual((yield dut.f.e[0].r_data),  1)
            self.assertEqual((yield dut.f.e[1].r_data),  1)
            self.assertEqual((yield dut.f.f   .r_data),  0b000)

            # Initiator read:

            yield dut.r_stb.eq(1)
            yield Delay()

            self.assertEqual((yield dut.f.a.w_ack), 1)
            self.assertEqual((yield dut.f.b.w_ack), 1)
            self.assertEqual((yield dut.f.f.w_ack), 1)

            yield dut.r_stb.eq(0)

            # Initiator write:

            yield dut.w_stb     .eq(1)
            yield dut.w_data.a  .eq(1)
            yield dut.w_data.b  .eq(0b010)
            yield dut.w_data.c.d.eq(0)
            yield dut.w_data.e  .eq(0)
            yield dut.w_data.f  .eq(0b110)
            yield
            yield Delay()

            self.assertEqual((yield dut.f.a   .r_stb), 0)
            self.assertEqual((yield dut.f.b   .r_stb), 1)
            self.assertEqual((yield dut.f.c.d .r_stb), 1)
            self.assertEqual((yield dut.f.e[0].r_stb), 1)
            self.assertEqual((yield dut.f.e[1].r_stb), 1)
            self.assertEqual((yield dut.f.f   .r_stb), 1)

            self.assertEqual((yield dut.f.c.d .r_data), 0)
            self.assertEqual((yield dut.f.b   .r_data), 0b101)
            self.assertEqual((yield dut.f.e[0].r_data), 0)
            self.assertEqual((yield dut.f.e[1].r_data), 0)
            self.assertEqual((yield dut.f.f   .r_data), 0b110)

            self.assertEqual((yield dut.r_data.a),   0)
            self.assertEqual((yield dut.r_data.b),   0b101)
            self.assertEqual((yield dut.r_data.c.d), 0)
            self.assertEqual((yield dut.r_data.f),   0b110)

            yield dut.w_stb.eq(0)

            # User write:

            yield dut.f.b.w_mask.eq(0b010)
            yield dut.f.b.w_data.eq(0b010)
            yield dut.f.f.w_mask.eq(0b010)
            yield dut.f.f.w_data.eq(0b010)
            yield
            yield Delay()

            self.assertEqual((yield dut.r_data.b), 0b111)
            self.assertEqual((yield dut.r_data.f), 0b100)

            self.assertEqual((yield dut.f.b.r_data), 0b111)
            self.assertEqual((yield dut.f.f.r_data), 0b100)

            yield dut.f.b.w_mask.eq(0)
            yield dut.f.f.w_mask.eq(0)

            # Concurrent writes:

            yield dut.w_stb.eq(1)
            yield dut.w_data.b.eq(0b111)
            yield dut.w_data.f.eq(0b111)

            yield dut.f.b.w_mask.eq(0b001)
            yield dut.f.b.w_data.eq(0b001)
            yield dut.f.f.w_mask.eq(0b111)
            yield dut.f.f.w_data.eq(0b111)
            yield
            yield Delay()

            self.assertEqual((yield dut.r_data.b),   0b001)
            self.assertEqual((yield dut.f.b.r_data), 0b001)
            self.assertEqual((yield dut.r_data.f),   0b111)
            self.assertEqual((yield dut.f.f.r_data), 0b111)

            yield dut.w_stb.eq(1)
            yield dut.f.b.w_mask.eq(0)
            yield dut.f.f.w_mask.eq(0)

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_sync_process(process)
        with sim.write_vcd(vcd_file=open("test.vcd", "w")):
            sim.run()
