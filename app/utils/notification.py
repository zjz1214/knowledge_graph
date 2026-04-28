"""
Notification utilities for the knowledge graph system.
"""

import winsound
import time


def beep(frequency: int = 440, duration: int = 300):
    """
    Play a beep sound.

    Args:
        frequency: Frequency in Hz (440 = A4 note)
        duration: Duration in milliseconds
    """
    try:
        winsound.Beep(frequency, duration)
    except Exception:
        pass


def notification_sound():
    """Play a notification sound (two short beeps)"""
    beep(440, 150)
    time.sleep(0.1)
    beep(880, 150)


def success_sound():
    """Play a success sound (ascending tone)"""
    beep(523, 100)  # C5
    time.sleep(0.08)
    beep(659, 100)  # E5
    time.sleep(0.08)
    beep(784, 150)  # G5


def error_sound():
    """Play an error sound (descending tone)"""
    beep(440, 100)
    time.sleep(0.05)
    beep(330, 200)


if __name__ == "__main__":
    print("Testing notification sounds...")
    print("Notification:")
    notification_sound()
    time.sleep(0.5)
    print("Success:")
    success_sound()
    time.sleep(0.5)
    print("Error:")
    error_sound()
    print("Done!")