#!/usr/bin/env python3
"""
AIR24 - Air Quality Event & Fault Injector
Digunakan untuk demonstrasi skenario uji gangguan secara instan saat demo UAS.
"""
import sys
import os
import argparse
import subprocess

def main():
    parser = argparse.ArgumentParser(description="Fault & Event Injector untuk Air Quality (Tim 3)")
    parser.add_argument("action", choices=["normal", "co2_spike", "pm_spike", "noise_spike", "stop", "crash"],
                        help="Pilih gangguan yang ingin diinjeksi")
    parser.add_argument("--device", default="aq-01", choices=["aq-01", "aq-02", "aq-03", "all"],
                        help="Target perangkat (default: aq-01)")
    args = parser.parse_args()

    mode_map = {
        "normal": "NORMAL",
        "co2_spike": "CO2_SPIKE",
        "pm_spike": "PM_SPIKE",
        "noise_spike": "NOISE_SPIKE",
        "stop": "STOP",
        "crash": "CRASH"
    }

    mode = mode_map[args.action]
    print(f"\n[INJECTOR] Menjalankan simulator dengan Mode: {mode} pada Perangkat: {args.device}...")
    sim_path = os.path.join(os.path.dirname(__file__), "simulator.py")
    
    cmd = [sys.executable, sim_path, "--mode", mode, "--device", args.device]
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n[INJECTOR] Dihentikan.")

if __name__ == "__main__":
    main()
