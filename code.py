import time
import board
import busio

import adafruit_ssd1306

from adafruit_bus_device.i2c_device import I2CDevice
import adafruit_dotstar

import usb_midi
import adafruit_midi

from adafruit_midi.control_change import ControlChange
from adafruit_midi.note_off import NoteOff
from adafruit_midi.note_on import NoteOn

from digitalio import DigitalInOut, Direction, Pull

cs = DigitalInOut(board.GP17)
cs.direction = Direction.OUTPUT
cs.value = 0

p = DigitalInOut(board.GP6)
p.direction = Direction.OUTPUT
p.value = 1

num_butts = 0x10

lights = adafruit_dotstar.DotStar(
    board.GP18, board.GP19, num_butts, brightness=0.1, auto_write=True
)

i2c = busio.I2C(board.GP5, board.GP4)
keypad = I2CDevice(i2c, 0x20)
midi = adafruit_midi.MIDI(midi_out=usb_midi.ports[1], out_channel=0)

oled_height = 32
oled_width = 128
# oled = adafruit_ssd1306.SSD1306_I2C(oled_width, oled_height, i2c)
# oled.fill(0)
# oled.show()


class LFO_STATE:
    off = 0
    slow = 1
    fast = 2


num_lfos = 8


def read_butts():
    pressed = [0] * 16
    with keypad:
        keypad.write(bytes([0x0]))
        result = bytearray(2)
        keypad.readinto(result)
        b = result[0] | result[1] << 8

        for i in range(0x0, len(pressed)):
            if not (1 << i) & b:
                pressed[i] = 1
            else:
                pressed[i] = 0
    return pressed


class Lfo:
    OFF = "off"
    SLOW = "slow"
    FAST = "fast"
    state = OFF
    idx = 0
    value = 0.0
    direction = +1
    held = False
    incs = {OFF: 0, SLOW: 0.01, FAST: 0.1}
    start = 0.0
    end = 1.0

    def __init__(self, idx):
        self.idx = idx

    def draw(self):
        line_height = oled_height // num_lfos
        # TODO consider removing gap
        # oled.fill_rect(
        #     0, self.idx * line_height, int(self.value * oled_width), line_height - 1, 1
        # )

    def pressed(self, butts):
        return butts[self.idx]

    def step(self):
        inc = self.incs[self.state]
        self.value += inc * self.direction
        if self.value <= self.start:
            self.value = self.start
            self.direction = 1
        elif self.value >= self.end:
            self.value = self.end
            self.direction = -1
        color_offset = lfo.int(128)
        if lfo.off:
            self.light((0, 0, 0))
        elif lfo.slow:
            self.light((255, color_offset, 0))
        elif lfo.fast:
            self.light((0, color_offset, 255))

    def light(self, color):
        lights[self.idx] = color

    def int(self, mul):
        return int(self.value * mul)

    def send(self):
        midi.send(ControlChange(self.idx, self.int(127)))

    @property
    def off(self):
        return self.state == Lfo.OFF

    @property
    def slow(self):
        return self.state == Lfo.SLOW

    @property
    def fast(self):
        return self.state == Lfo.FAST

    def press(self):
        if self.held:
            return
        elif self.off:
            self.state = Lfo.SLOW
        elif self.slow:
            self.state = Lfo.FAST
        elif self.fast:
            self.state = Lfo.OFF
        self.held = True

    def release(self):
        self.held = False


bpm_mode = False
bpm = 128

lfos = [Lfo(0)] * num_lfos

for idx in range(num_lfos):
    lfos[idx] = Lfo(idx)


class Mode:
    NORMAL = "normal"
    TEACHING = "teaching"
    SET_BPM = "bpm"
    SET_LIMIT_START = "limit start"
    SET_LIMIT_END = "limit end"
    SET_CHANNEL = "channel"
    current = NORMAL


mode = Mode()

while True:
    # todo use bpm
    time.sleep(0.1)
    # oled.fill(0)
    # todo set bpm mode (press B then type a number then press F to select. press B again to cancel)
    # todo set channel mode (press C, type number to set midi channel, then F to select. press B to cancel)
    # in bpm and channel mode: numbers should be white, B should be red and F should be green
    # todo teaching mode (press F, disables LFO, press a button to send the CC for that lfo once)
    # todo set limits mode (press A, press a control, press a number and then select start (0-A) and end (0-A))

    if mode.current == mode.TEACHING:
        continue

    butts = read_butts()

    for lfo in lfos:
        lfo.step()

        if not lfo.off:
            lfo.send()

        lfo.draw()

        if lfo.pressed(butts):
            lfo.press()
        else:
            lfo.release()

    # oled.show()
    lights.show()
