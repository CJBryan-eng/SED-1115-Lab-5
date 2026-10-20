"""
SED 1115 - Lab 5: Time perception game (MicroPython, Raspberry Pi Pico)

Press the button to start, count 15 seconds in your head, press again.
The elapsed time (whole seconds, read from the DS3231 RTC) is printed
and appended to log.txt. Repeats until the program is stopped (Ctrl+C),
at which point the log file is closed so everything is saved to flash.
"""

from machine import Pin, I2C
import time

# ---------------- Configuration ----------------
RTC_ADDR = 0x68          # I2C address of the DS3231 chip
TARGET_SECONDS = 15      # what the player is trying to count
BUTTON_PIN = 22          # SW5 on the expansion board (GPIO10)
SET_RTC_ON_START = False # set True ONCE to program the clock, then False again

# I2C channel 1: SDA = GPIO14, SCL = GPIO15 (wired to J11)
i2c = I2C(1, sda=Pin(14), scl=Pin(15))

# Expansion-board buttons are wired to 3V3 when pressed, so use pull-down.
# If your button reads inverted, change to Pin.PULL_UP and swap 0/1 below.
button = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_DOWN)


# ---------------- BCD helpers ----------------
def bcd_to_int(bcd):
    """Convert a BCD byte (e.g. 0x45) to an integer (45)."""
    return (bcd >> 4) * 10 + (bcd & 0x0F)


def int_to_bcd(value):
    """Convert an integer (45) to a BCD byte (0x45)."""
    return ((value // 10) << 4) | (value % 10)


# ---------------- RTC functions ----------------
def set_rtc(year, month, date, weekday, hour, minute, second):
    """Write date/time to the DS3231 (24-hour format, year 2000-2099)."""
    data = bytes([
        int_to_bcd(second),
        int_to_bcd(minute),
        int_to_bcd(hour),          # bit 6 = 0 -> 24-hour mode
        int_to_bcd(weekday),
        int_to_bcd(date),
        int_to_bcd(month),         # century bit left at 0
        int_to_bcd(year % 100),
    ])
    i2c.writeto_mem(RTC_ADDR, 0x00, data)


def read_rtc():
    """Read all 7 time registers in one transfer.
    Returns (year, month, date, weekday, hour, minute, second)."""
    buf = i2c.readfrom_mem(RTC_ADDR, 0x00, 7)

    second = bcd_to_int(buf[0] & 0x7F)
    minute = bcd_to_int(buf[1] & 0x7F)

    hour_reg = buf[2]
    if hour_reg & 0x40:                       # 12-hour mode
        hour = bcd_to_int(hour_reg & 0x1F)    # 1-12
        is_pm = bool(hour_reg & 0x20)
        if hour == 12:
            hour = 0
        if is_pm:
            hour += 12
    else:                                     # 24-hour mode
        hour = bcd_to_int(hour_reg & 0x3F)

    weekday = buf[3] & 0x07
    date = bcd_to_int(buf[4] & 0x3F)
    month = bcd_to_int(buf[5] & 0x1F)
    year = 2000 + bcd_to_int(buf[6])
    return year, month, date, weekday, hour, minute, second


def seconds_of_day():
    """Seconds since midnight according to the RTC."""
    _, _, _, _, h, m, s = read_rtc()
    return h * 3600 + m * 60 + s


def timestamp_string():
    """Human-readable RTC timestamp: YYYY-MM-DD HH:MM:SS."""
    y, mo, d, _, h, mi, s = read_rtc()
    return "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(y, mo, d, h, mi, s)


# ---------------- Button helper ----------------
def wait_for_press():
    """Block until the button is pressed and released (with debouncing)."""
    while button.value() == 0:
        time.sleep_ms(5)
    time.sleep_ms(50)                 # debounce press
    while button.value() == 1:
        time.sleep_ms(5)
    time.sleep_ms(50)                 # debounce release


# ---------------- Main program ----------------
def main():
    if SET_RTC_ON_START:
        # EDIT to the current date/time, run once, then set the flag to False.
        # (year, month, date, weekday 1-7, hour, minute, second)
        set_rtc(2026, 10, 13, 2, 12, 0, 0)

    # Open the log ONCE (append mode keeps earlier trials) to limit flash wear.
    log = open("log.txt", "a")
    try:
        trial = 0
        while True:
            print("\nPress the button to START, then press again after "
                  "{} seconds.".format(TARGET_SECONDS))
            wait_for_press()
            start = seconds_of_day()
            start_stamp = timestamp_string()
            print("Counting... (don't look at a clock!)")

            wait_for_press()
            end = seconds_of_day()

            # modulo handles the rare case of crossing midnight
            elapsed = (end - start) % 86400
            trial += 1
            error = elapsed - TARGET_SECONDS

            print("Trial {}: {} s (error {:+d} s)".format(trial, elapsed, error))

            # One line per trial: "timestamp,elapsed_seconds"
            log.write("{},{}\n".format(start_stamp, elapsed))
            log.flush()               # push the buffer to flash now
    except KeyboardInterrupt:
        print("\nStopped by user.")
    finally:
        log.close()                   # always runs, so the log is saved
        print("Log file closed.")


main()
