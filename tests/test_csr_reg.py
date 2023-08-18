# amaranth: UnusedElaboratable=no

import unittest
from amaranth import *
from amaranth.lib import data
from amaranth.sim import *

from amaranth_soc.csr.reg import *
from amaranth_soc.csr import field


class FieldPortTestCase(unittest.TestCase):
    def test_shape_1_ro(self):
        port = FieldPort(1, "r")
        self.assertEqual(port.shape, unsigned(1))
        self.assertEqual(port.access, FieldPort.Access.R)
        self.assertEqual(port.r_data.shape(), unsigned(1))
        self.assertEqual(port.r_stb .shape(), unsigned(1))
        self.assertEqual(port.w_data.shape(), unsigned(1))
        self.assertEqual(port.w_stb .shape(), unsigned(1))
        self.assertEqual(repr(port), "FieldPort(unsigned(1), Access.R)")

    def test_shape_8_rw(self):
        port = FieldPort(8, "rw")
        self.assertEqual(port.shape, unsigned(8))
        self.assertEqual(port.access, FieldPort.Access.RW)
        self.assertEqual(port.r_data.shape(), unsigned(8))
        self.assertEqual(port.r_stb .shape(), unsigned(1))
        self.assertEqual(port.w_data.shape(), unsigned(8))
        self.assertEqual(port.w_stb .shape(), unsigned(1))
        self.assertEqual(repr(port), "FieldPort(unsigned(8), Access.RW)")

    def test_shape_10_wo(self):
        port = FieldPort(10, "w")
        self.assertEqual(port.shape, unsigned(10))
        self.assertEqual(port.access, FieldPort.Access.W)
        self.assertEqual(port.r_data.shape(), unsigned(10))
        self.assertEqual(port.r_stb .shape(), unsigned(1))
        self.assertEqual(port.w_data.shape(), unsigned(10))
        self.assertEqual(port.w_stb .shape(), unsigned(1))
        self.assertEqual(repr(port), "FieldPort(unsigned(10), Access.W)")

    def test_shape_0_rw(self):
        port = FieldPort(0, "rw")
        self.assertEqual(port.shape, unsigned(0))
        self.assertEqual(port.access, FieldPort.Access.RW)
        self.assertEqual(port.r_data.shape(), unsigned(0))
        self.assertEqual(port.r_stb .shape(), unsigned(1))
        self.assertEqual(port.w_data.shape(), unsigned(0))
        self.assertEqual(port.w_stb .shape(), unsigned(1))
        self.assertEqual(repr(port), "FieldPort(unsigned(0), Access.RW)")

    def test_shape_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"Field shape must be a shape-castable object, not 'foo'"):
            port = FieldPort("foo", "rw")

    def test_access_wrong(self):
        with self.assertRaisesRegex(ValueError,
                r"Access mode must be one of \"r\", \"w\", or \"rw\", not 'wo'"):
            port = FieldPort(8, "wo")


def _compatible_fields(a, b):
    return isinstance(a, Field) and type(a) == type(b) and \
           a.shape == b.shape and a.access == b.access


class FieldTestCase(unittest.TestCase):
    def test_simple(self):
        field = Field(unsigned(4), "rw")
        self.assertEqual(field.shape, unsigned(4))
        self.assertEqual(field.access, FieldPort.Access.RW)
        self.assertEqual(repr(field.port), "FieldPort(unsigned(4), Access.RW)")
        self.assertEqual(field.data.shape(), unsigned(4))

    def test_compatible(self):
        self.assertTrue(_compatible_fields(Field(unsigned(4), "rw"),
                                           Field(unsigned(4), FieldPort.Access.RW)))
        self.assertFalse(_compatible_fields(Field(unsigned(3), "r" ), Field(unsigned(4), "r")))
        self.assertFalse(_compatible_fields(Field(unsigned(4), "rw"), Field(unsigned(4), "w")))
        self.assertFalse(_compatible_fields(Field(unsigned(4), "rw"), Field(unsigned(4), "r")))
        self.assertFalse(_compatible_fields(Field(unsigned(4), "r" ), Field(unsigned(4), "w")))

    def test_wrong_shape(self):
        with self.assertRaisesRegex(TypeError,
                r"Field shape must be a shape-castable object, not 'foo'"):
            Field("foo", "rw")

    def test_wrong_access(self):
        with self.assertRaisesRegex(ValueError,
                r"Access mode must be one of \"r\", \"w\", or \"rw\", not 'wo'"):
            Field(8, "wo")


class FieldMapTestCase(unittest.TestCase):
    def test_simple(self):
        field_map = FieldMap({
            "a": Field(unsigned(1), "r"),
            "b": Field(signed(3), "rw"),
            "c": FieldMap({
                "d": Field(unsigned(4), "rw"),
            }),
        })
        self.assertTrue(_compatible_fields(field_map["a"], Field(unsigned(1), "r")))
        self.assertTrue(_compatible_fields(field_map["b"], Field(signed(3), "rw")))
        self.assertTrue(_compatible_fields(field_map["c"]["d"], Field(unsigned(4), "rw")))

        self.assertTrue(_compatible_fields(field_map.a, Field(unsigned(1), "r")))
        self.assertTrue(_compatible_fields(field_map.b, Field(signed(3), "rw")))
        self.assertTrue(_compatible_fields(field_map.c.d, Field(unsigned(4), "rw")))

        self.assertEqual(len(field_map), 3)

    def test_iter(self):
        field_map = FieldMap({
            "a": Field(unsigned(1), "r"),
            "b": Field(signed(3), "rw")
        })
        self.assertEqual(list(field_map.items()), [
            ("a", field_map["a"]),
            ("b", field_map["b"]),
        ])

    def test_flatten(self):
        field_map = FieldMap({
            "a": Field(unsigned(1), "r"),
            "b": Field(signed(3), "rw"),
            "c": FieldMap({
                "d": Field(unsigned(4), "rw"),
            }),
        })
        self.assertEqual(list(field_map.flatten()), [
            (("a",), field_map["a"]),
            (("b",), field_map["b"]),
            (("c", "d"), field_map["c"]["d"]),
        ])

    def test_wrong_mapping(self):
        with self.assertRaisesRegex(TypeError,
                r"Fields must be provided as a non-empty mapping, not 'foo'"):
            FieldMap("foo")

    def test_wrong_field_key(self):
        with self.assertRaisesRegex(TypeError,
                r"Field name must be a non-empty string, not 1"):
            FieldMap({1: Field(unsigned(1), "rw")})
        with self.assertRaisesRegex(TypeError,
                r"Field name must be a non-empty string, not ''"):
            FieldMap({"": Field(unsigned(1), "rw")})

    def test_wrong_field_value(self):
        with self.assertRaisesRegex(TypeError,
                r"Field must be a Field or a FieldMap or a FieldArray, not unsigned\(1\)"):
            FieldMap({"a": unsigned(1)})

    def test_getitem_wrong_key(self):
        with self.assertRaises(KeyError):
            FieldMap({"a": Field(unsigned(1), "rw")})["b"]


class FieldArrayTestCase(unittest.TestCase):
    def test_simple(self):
        field_array = FieldArray(Field(unsigned(2), "rw"), length=8)
        self.assertEqual(len(field_array), 8)
        for i in range(8):
            self.assertTrue(_compatible_fields(field_array[i], Field(unsigned(2), "rw")))

    def test_dim_2(self):
        field_array = FieldArray(FieldArray(Field(unsigned(1), "rw"), length=4), length=4)

        self.assertEqual(len(field_array), 4)
        for i in range(4):
            for j in range(4):
                self.assertTrue(_compatible_fields(field_array[i][j], Field(1, "rw")))

    def test_nested(self):
        field_array = FieldArray(
                FieldMap({
                    "a": Field(unsigned(4), "rw"),
                    "b": FieldArray(Field(unsigned(1), "rw"), length=4),
                }), length=4)

        self.assertEqual(len(field_array), 4)

        for i in range(4):
            self.assertTrue(_compatible_fields(field_array[i]["a"], Field(unsigned(4), "rw")))
            for j in range(4):
                self.assertTrue(_compatible_fields(field_array[i]["b"][j],
                                                   Field(unsigned(1), "rw")))

    def test_iter(self):
        field_array = FieldArray(Field(1, "rw"), length=3)
        self.assertEqual(list(field_array), [
            field_array[i] for i in range(3)
        ])

    def test_flatten(self):
        field_array = FieldArray(
                FieldMap({
                    "a": Field(4, "rw"),
                    "b": FieldArray(Field(1, "rw"), length=2),
                }), length=2)
        self.assertEqual(list(field_array.flatten()), [
            ((0, "a"), field_array[0]["a"]),
            ((0, "b", 0), field_array[0]["b"][0]),
            ((0, "b", 1), field_array[0]["b"][1]),
            ((1, "a"), field_array[1]["a"]),
            ((1, "b", 0), field_array[1]["b"][0]),
            ((1, "b", 1), field_array[1]["b"][1]),
        ])

    def test_wrong_field(self):
        with self.assertRaisesRegex(TypeError,
                r"Field must be a Field or a FieldMap or a FieldArray, not 'foo'"):
            FieldArray("foo", 4)

    def test_wrong_length(self):
        with self.assertRaisesRegex(TypeError,
                r"Field array length must be a positive integer, not 'foo'"):
            FieldArray(Field(1, "rw"), "foo")
        with self.assertRaisesRegex(TypeError,
                r"Field array length must be a positive integer, not 0"):
            FieldArray(Field(1, "rw"), 0)

    def test_getitem_wrong_key(self):
        with self.assertRaisesRegex(TypeError,
                r"Cannot index field array with 'a'"):
            FieldArray(Field(1, "rw"), 1)["a"]
        # with self.assertRaises(IndexError):
            # FieldArray(Field(1, "rw"), 1)[1]
        # with self.assertRaises(IndexError):
            # FieldArray(Field(1, "rw"), 1)[-2]


class RegisterTestCase(unittest.TestCase):
    def test_simple(self):
        reg = Register("rw", FieldMap({
            "a": field.R(unsigned(1)),
            "b": field.RW1C(unsigned(3)),
            "c": FieldMap({"d": field.RW(signed(2))}),
            "e": FieldArray(field.W(unsigned(1)), length=2),
        }))

        self.assertTrue(_compatible_fields(reg.f.a, field.R(unsigned(1))))
        self.assertTrue(_compatible_fields(reg.f.b, field.RW1C(unsigned(3))))
        self.assertTrue(_compatible_fields(reg.f.c.d, field.RW(signed(2))))
        self.assertTrue(_compatible_fields(reg.f.e[0], field.W(unsigned(1))))
        self.assertTrue(_compatible_fields(reg.f.e[1], field.W(unsigned(1))))

        self.assertEqual(reg.element.width, 8)
        self.assertEqual(reg.element.access.readable(), True)
        self.assertEqual(reg.element.access.writable(), True)

    def test_annotations(self):
        class MockRegister(Register):
            a: field.R(unsigned(1))
            b: field.RW1C(unsigned(3))
            c: FieldMap({"d": field.RW(signed(2))})
            e: FieldArray(field.W(unsigned(1)), length=2)

            foo: unsigned(42)

        reg = MockRegister("rw")

        self.assertTrue(_compatible_fields(reg.f.a, field.R(unsigned(1))))
        self.assertTrue(_compatible_fields(reg.f.b, field.RW1C(unsigned(3))))
        self.assertTrue(_compatible_fields(reg.f.c.d, field.RW(signed(2))))
        self.assertTrue(_compatible_fields(reg.f.e[0], field.W(unsigned(1))))
        self.assertTrue(_compatible_fields(reg.f.e[1], field.W(unsigned(1))))

        self.assertEqual(reg.element.width, 8)
        self.assertEqual(reg.element.access.readable(), True)
        self.assertEqual(reg.element.access.writable(), True)

    def test_iter(self):
        reg = Register("rw", FieldMap({
            "a": field.R(unsigned(1)),
            "b": field.RW1C(unsigned(3)),
            "c": FieldMap({"d": field.RW(signed(2))}),
            "e": FieldArray(field.W(unsigned(1)), length=2),
        }))
        self.assertEqual(list(reg), [
            (("a",), reg.f.a),
            (("b",), reg.f.b),
            (("c", "d"), reg.f.c.d),
            (("e", 0), reg.f.e[0]),
            (("e", 1), reg.f.e[1]),
        ])

    def test_sim(self):
        dut = Register("rw", FieldMap({
            "a": field.R(unsigned(1)),
            "b": field.RW1C(unsigned(3), reset=0b111),
            "c": FieldMap({"d": field.RW(signed(2), reset=-1)}),
            "e": FieldArray(field.W(unsigned(1)), length=2),
            "f": field.RW1S(unsigned(3)),
        }))

        def process():
            # Check reset values:

            self.assertEqual((yield dut.f.a.data),    0)
            self.assertEqual((yield dut.f.b.data),    0b111)
            self.assertEqual((yield dut.f.c.d.data), -1)
            self.assertEqual((yield dut.f.f.data),    0b000)

            """
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
            """

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_sync_process(process)
        with sim.write_vcd(vcd_file=open("test.vcd", "w")):
            sim.run()


class ClusterTestCase(unittest.TestCase):
    def test_memory_map(self):
        cluster = Cluster(addr_width=1, data_width=8, name="cluster")
        self.assertEqual(cluster.memory_map.addr_width, 1)
        self.assertEqual(cluster.memory_map.data_width, 8)
        self.assertEqual(cluster.memory_map.name, "cluster")

    def test_add(self):
        cluster = Cluster(addr_width=1, data_width=8, name="cluster")
        reg_0   = Register("rw", FieldMap({"a": field.RW(8)}))
        reg_1   = Register("r",  FieldMap({"b": field.R (8)}))
        self.assertEqual(cluster.add(reg_0, name="reg_0", addr=0), reg_0)
        self.assertEqual(cluster.add(reg_1, name="reg_1", addr=1), reg_1)
        self.assertEqual(list(cluster.memory_map.resources()), [
            (reg_0.element, "reg_0", (0, 1)),
            (reg_1.element, "reg_1", (1, 2)),
        ])

    def test_add_frozen(self):
        cluster = Cluster(addr_width=1, data_width=8, name="cluster")
        reg_0   = Register("rw", FieldMap({"a": field.RW(8)}))
        cluster.freeze()
        with self.assertRaisesRegex(ValueError,
                r"Memory map has been frozen\. Cannot add resource Element\(8, Access\.RW\)"):
            cluster.add(reg_0, name="reg_0", addr=0)

    def test_add_wrong_type(self):
        cluster = Cluster(addr_width=1, data_width=8, name="cluster")
        with self.assertRaisesRegex(TypeError,
                r"Register must be an instance of csr\.Register, not 'foo'"):
            cluster.add("foo", name="reg", addr=0)

    def test_add_access_ro(self):
        cluster = Cluster(addr_width=1, data_width=8, name="cluster", access="r")
        reg_0   = Register("rw", FieldMap({"a": field.RW(8)}))
        with self.assertRaisesRegex(ValueError,
                r"Register reg_0 is writable, but cluster access mode is Access.R"):
            cluster.add(reg_0, name="reg_0", addr=0)

    def test_add_access_wo(self):
        cluster = Cluster(addr_width=1, data_width=8, name="cluster", access="w")
        reg_0   = Register("rw", FieldMap({"a": field.RW(8)}))
        with self.assertRaisesRegex(ValueError,
                r"Register reg_0 is readable, but cluster access mode is Access.W"):
            cluster.add(reg_0, name="reg_0", addr=0)
