from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from .engine import reconstruct


def main(argv=None):
    parser = argparse.ArgumentParser(description='Experimental fact-preserving reconstruction, not verified watermark removal')
    parser.add_argument('--text')
    parser.add_argument('--file', type=Path)
    parser.add_argument('--budget', type=int, default=32)
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--max-states', type=int, default=20000)
    args = parser.parse_args(argv)
    if args.text is not None and args.file is not None:
        parser.error('choose --text or --file')
    try:
        if args.text is not None:
            source = args.text
        elif args.file is not None:
            with args.file.open(encoding='utf-8', newline='') as stream:
                source = stream.read(100001)
        else:
            buffer = getattr(sys.stdin, 'buffer', None)
            source = buffer.read(400001).decode('utf-8') if buffer is not None else sys.stdin.read(100001)
        result = reconstruct(source, budget=args.budget, max_states=args.max_states)
        if args.json:
            print(json.dumps({'text': result.text, 'receipt': result.receipt()}, ensure_ascii=True, indent=2))
        else:
            buffer = getattr(sys.stdout, 'buffer', None)
            if buffer is None:
                sys.stdout.write(result.text)
            else:
                buffer.write(result.text.encode('utf-8'))
                buffer.flush()
            sys.stderr.write(json.dumps(result.receipt(), ensure_ascii=True) + '\n')
        return 0 if result.status in {'changed', 'unchanged'} else 3
    except (OSError, UnicodeError, ValueError, TypeError) as error:
        print(f'reconstruction: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
