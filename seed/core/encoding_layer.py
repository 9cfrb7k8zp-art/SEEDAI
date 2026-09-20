# ==========================================================
# SEED ENCODING LAYER
# Converts digital symbols ↔ physical carrier
# Supports: NRZ, Manchester, 4-QAM
# Stable, system-ready version
# ==========================================================

import logging

logger = logging.getLogger("SEEDEncoding")


class SymbolEncoder:
    """
    Encodes/decodes data into symbols for transmission.
    Supports NRZ, Manchester, and 4-QAM.
    """

    def __init__(self, mode="NRZ"):
        self.mode = mode.upper()
        self.symbol_map = self._init_symbol_map()
        self.inverse_map = {v: k for k, v in self.symbol_map.items()}

    # ======================================================
    # ENCODE
    # ======================================================
    def encode(self, data_bytes):
        """
        Converts bytes → symbols
        Handles multi-bit symbols for 4-QAM
        """
        symbols = []
        if self.mode == "4-QAM":
            # Process 2 bits per symbol
            for b in data_bytes:
                for i in range(0, 8, 2):
                    bits = (b >> (6 - i)) & 0b11
                    symbols.append(self._map_symbol(bits))
        else:
            for b in data_bytes:
                for bit_pos in range(8):
                    bit = (b >> (7 - bit_pos)) & 0x1
                    symbols.append(self._map_symbol(bit))
        return symbols

    # ======================================================
    # DECODE
    # ======================================================
    def decode(self, symbols):
        """
        Converts symbols → bytes
        """
        bits = []
        for s in symbols:
            bit = self._inverse_map_symbol(s)
            if self.mode == "4-QAM":
                # Convert 2-bit symbol to list of bits
                bits.append((bit >> 1) & 1)
                bits.append(bit & 1)
            else:
                bits.append(bit)

        bytes_out = []
        for i in range(0, len(bits), 8):
            byte = 0
            for j in range(8):
                if i + j < len(bits):
                    byte |= (bits[i + j] << (7 - j))
            bytes_out.append(byte)
        return bytes_out

    # ======================================================
    # INTERNAL SYMBOL MAPPING
    # ======================================================
    def _init_symbol_map(self):
        if self.mode == "NRZ":
            return {0: -1.0, 1: 1.0}
        elif self.mode == "MANCHESTER":
            return {0: (-1, 1), 1: (1, -1)}
        elif self.mode == "4-QAM":
            # 2 bits per symbol
            return {
                0b00: (1, 1),
                0b01: (-1, 1),
                0b10: (1, -1),
                0b11: (-1, -1),
            }
        else:
            logger.warning(f"[SymbolEncoder] Unknown encoding mode '{self.mode}', defaulting to NRZ")
            return {0: -1.0, 1: 1.0}

    def _map_symbol(self, bit_or_bits):
        try:
            return self.symbol_map[bit_or_bits]
        except KeyError:
            logger.warning(f"[SymbolEncoder] Unknown bit value '{bit_or_bits}', defaulting to 0")
            return self.symbol_map.get(0, -1.0)

    def _inverse_map_symbol(self, symbol):
        if self.mode == "NRZ":
            return 1 if symbol > 0 else 0
        elif self.mode == "MANCHESTER":
            return 1 if symbol[0] > symbol[1] else 0
        elif self.mode == "4-QAM":
            for k, v in self.symbol_map.items():
                if v == symbol:
                    return k
            logger.warning(f"[SymbolEncoder] Unknown 4-QAM symbol {symbol}, defaulting to 0b00")
            return 0b00
        else:
            return 1 if symbol > 0 else 0
