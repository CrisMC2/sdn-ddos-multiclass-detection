#!/usr/bin/env python3
"""Compatibilidad: un ataque del campus (los infectados, no un solo host)."""
import sys

import capture_campus
from roles import SCENARIOS

if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] not in SCENARIOS or sys.argv[1] == 'baseline':
        print('Uso: python3 capture_attack.py <%s> [segundos] [salida.pcap]' % '|'.join(
            s for s in SCENARIOS if s != 'baseline'))
        raise SystemExit(1)
    capture_campus.main()
