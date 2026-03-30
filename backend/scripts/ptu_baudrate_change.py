#!/usr/bin/env python3
import argparse
import re
import sys
import time

SUPPORTED_BAUDS = {9600: 1, 115200: 2}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Change the PTU controller baud rate (runs standalone, app must be stopped)."
    )
    parser.add_argument(
        "--port", required=True,
        help="Serial port the PTU is connected to (e.g. COM5 or /dev/ttyUSB0)",
    )
    parser.add_argument(
        "--current-baud", type=int, default=9600,
        choices=list(SUPPORTED_BAUDS),
        help="Baud rate the PTU is currently using (default: 9600)",
    )
    parser.add_argument(
        "--new-baud", type=int, required=True,
        choices=list(SUPPORTED_BAUDS),
        help="Baud rate to switch the PTU to",
    )
    args = parser.parse_args()

    if args.current_baud == args.new_baud:
        print(f"[INFO] PTU is already at {args.current_baud} baud — nothing to do.")
        sys.exit(0)

    try:
        import serial
    except ImportError:
        print("[ERROR] pyserial is not installed. Run: pip install pyserial")
        sys.exit(1)

    baud_param = SUPPORTED_BAUDS[args.new_baud]
    h93_cmd    = f"H93,{baud_param},1,20000E".encode("ascii")

    # ── Step 1: open at current baud ─────────────────────────────────────────
    print(f"[1/4] Opening {args.port} at {args.current_baud} baud …")
    try:
        ser = serial.Serial(
            port=args.port,
            baudrate=args.current_baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=1.0,
            write_timeout=1.0,
        )
    except serial.SerialException as e:
        print(f"[ERROR] Could not open port: {e}")
        sys.exit(1)

    # ── Step 2: send H93 ─────────────────────────────────────────────────────
    print(f"[2/4] Sending baud change command: {h93_cmd.decode()} …")
    try:
        ser.write(h93_cmd)
        ser.flush()
    except Exception as e:
        print(f"[ERROR] Write failed: {e}")
        ser.close()
        sys.exit(1)

    ser.close()
    print(f"      Command sent. Device is restarting …")

    # ── Step 3: wait for device restart ──────────────────────────────────────
    print("[3/4] Waiting 2 s for device to restart …")
    time.sleep(2.0)

    # ── Step 4: reopen at new baud and verify with H99E ───────────────────────
    print(f"[4/4] Reopening {args.port} at {args.new_baud} baud and verifying …")
    try:
        ser2 = serial.Serial(
            port=args.port,
            baudrate=args.new_baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=2.0,
            write_timeout=1.0,
        )
    except serial.SerialException as e:
        print(f"[ERROR] Could not reopen port at {args.new_baud} baud: {e}")
        print("        The baud change may have failed. Try power-cycling the PTU.")
        sys.exit(1)

    # Send H99E and look for the baud confirmation line
    h99_delay = 0.5 if args.new_baud <= 9600 else 0.1
    try:
        ser2.write(b"H99E")
        ser2.flush()
        time.sleep(h99_delay)
        raw = ser2.read(512)
        ser2.close()
    except Exception as e:
        print(f"[ERROR] Verification read failed: {e}")
        sys.exit(1)

    if not raw:
        print("[WARN] No response from device — port opened but device may not be ready.")
        print("       Try power-cycling the PTU and running this script again.")
        sys.exit(1)

    text = raw.decode("ascii", errors="ignore")

    # Look for "Serial_baud = <value>" in H99E response
    m = re.search(r"Serial_baud\s*=\s*(\d+)", text, re.IGNORECASE)
    confirmed_baud = int(m.group(1)) if m else None

    print()
    print("─── Device response (H99E) ───────────────────────────────────────")
    print(text.strip())
    print("──────────────────────────────────────────────────────────────────")
    print()

    if confirmed_baud == args.new_baud:
        print(f"[OK] Baud rate successfully changed to {args.new_baud}.")
    elif confirmed_baud is not None:
        print(f"[WARN] Device reports baud={confirmed_baud}, expected {args.new_baud}.")
    else:
        # Response arrived but baud line not found — still probably worked
        print(f"[OK] Device responded at {args.new_baud} baud (baud line not found in response).")

    print()
    print("Next steps:")
    print(f"  1. Open backend/.env and set:  PTU_BAUD={args.new_baud}")
    print("  2. Restart the main application.")


if __name__ == "__main__":
    main()