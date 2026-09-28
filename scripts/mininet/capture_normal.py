#!/usr/bin/env python3
"""Compatibilidad: el trafico normal ahora es el baseline del campus."""
import sys

import capture_campus

if __name__ == '__main__':
    duration = sys.argv[1] if len(sys.argv) > 1 else '120'
    rest = sys.argv[2:]
    sys.argv = [sys.argv[0], 'baseline', duration] + rest
    capture_campus.main()
