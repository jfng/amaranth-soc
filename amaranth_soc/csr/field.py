from amaranth_soc import csr


__all__ = ["R", "W", "RW", "RW1C", "RW1S"]


def _read_field(self, field):
    return field

def _write_field(self, field, value):
    return value

def _clear_field(self, field, value):
    return field & ~value

def _set_field(self, field, value):
    return field | value


class R(csr.GenericField,
        intr_read  = _read_field,
        intr_write = None,
        user_read  = _read_field,
        user_write = _write_field):
    pass


class W(csr.GenericField,
        intr_read  = None,
        intr_write = _write_field,
        user_read  = _read_field,
        user_write = None):
    pass


class RW(csr.GenericField,
         intr_read  = _read_field,
         intr_write = _write_field,
         user_read  = _read_field,
         user_write = None):
    pass


class RW1C(csr.GenericField,
           intr_read  = _read_field,
           intr_write = _clear_field,
           user_read  = _read_field,
           user_write = _set_field):
    pass


class RW1S(csr.GenericField,
           intr_read  = _read_field,
           intr_write = _set_field,
           user_read  = _read_field,
           user_write = _clear_field):
    pass
