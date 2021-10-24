from adafruit_midi.midi_message import MIDIMessage
import board
import busio

from adafruit_bus_device.i2c_device import I2CDevice
import adafruit_dotstar

import usb_midi
import adafruit_midi

from adafruit_midi.control_change import ControlChange

from ulab import numpy as math

from digitalio import DigitalInOut, Direction, Pull

cs = DigitalInOut(board.GP17)
cs.direction = Direction.OUTPUT
cs.value = 0

p = DigitalInOut(board.GP6)
p.direction = Direction.OUTPUT
p.value = 1

i2c = busio.I2C(board.GP5, board.GP4)
keypad = I2CDevice(i2c, 0x20)
midi = adafruit_midi.MIDI(midi_out=usb_midi.ports[1], out_channel=0)


class Butts:
    length = 0x10
    held = [False] * length
    pressed = [False] * length

    def read(self):
        with keypad:
            keypad.write(bytes([0x0]))
            result = bytearray(2)
            keypad.readinto(result)
            b = result[0] | result[1] << 8

            for i in range(0x0, Butts.length):
                p = not (1 << i) & b
                if p:
                    if self.held[i]:
                        self.pressed[i] = False
                    else:
                        self.pressed[i] = True
                        self.held[i] = True
                else:
                    self.pressed[i] = False
                    self.held[i] = False
        return self.pressed


lights = adafruit_dotstar.DotStar(board.GP18,
                                  board.GP19,
                                  Butts.length,
                                  brightness=1,
                                  auto_write=True)

butts = Butts()


class Control:
    idx = 0

    def __init__(self, idx):
        self.idx = idx

    def light(self, color):
        lights[self.idx] = color


class Lfo(Control):
    length = 0x8
    idx = 0
    direction = +1
    tick = 1
    start = 0x0
    end = 0xA
    speed = 0x5
    on = False

    def __init__(self, idx):
        self.idx = idx

    def step(self):
        self.tick += 1

    def update_lights(self):
        if self.tick % 3:
            return
        i = lfo.int(255)
        redness = (math.sin(2**math.pi / self.tick) + 1) * 64
        if lfo.on:
            self.light((redness, i // (self.speed + 1), i))
        else:
            self.light((0, 0, 0))

    @property
    def sin(self):
        speed = 2**(12 - self.speed)
        period = (2 * math.pi) / speed
        amp = (self.start - self.end) / 10
        offset = self.start / 10
        sin = math.sin(period * self.tick)
        return (amp * sin) + offset

    @property
    def value(self):
        return (self.sin + 1) / 2

    def int(self, mul):
        return int(self.value * mul)

    def send(self):
        midi.send(ControlChange(self.idx, self.int(127)))

    def press(self, pressed_buttons):
        if pressed_buttons[self.idx]:
            self.on = not self.on
            self.light((0, 0, 0))


bpm_mode = False
bpm = 128

lfos = [Lfo(x) for x in range(Lfo.length)]


class Mode:
    NORMAL = "normal"
    TEACHING = "teaching"
    SET_SPEED_CHOOSE_LFO = "speed lfo"
    SET_SPEED = "speed set"
    SET_LIMIT_CHOOSE_LFO = "limit lfo"
    SET_LIMIT_START = "limit start"
    SET_LIMIT_END = "limit end"
    SET_CHANNEL = "channel"
    current = NORMAL

    @property
    def normal(self):
        return self.current == Mode.NORMAL

    @property
    def teaching(self):
        return self.current == Mode.TEACHING

    def become_normal(self):
        self.current = Mode.NORMAL


mode = Mode()

# for the type
setting_lfo = Lfo(-1)

pmode = None

while True:
    # todo set channel mode (press C, type number to set midi channel, then F to select. press B to cancel)
    # todo set cc number mode (press C, then C, then select an lfo, type number to set cc, then F to select. press B to cancel)
    butts.read()
    if pmode != mode.current:
        for idx in range(Butts.length):
            lights[idx] = (0, 0, 0)
        if mode.current == mode.NORMAL:
            lights[0xA] = (10, 20, 40)
            lights[0xB] = (50, 30, 10)
            lights[0xF] = (50, 20, 20)
        pmode = mode.current

    for lfo in lfos:
        if lfo.on and not mode.teaching:
            lfo.step()
            lfo.send()

        if mode.normal:
            lfo.press(butts.pressed)
            lfo.update_lights()

    # todo deal with repetition
    if mode.teaching:
        lights[0xF] = (255, 0, 0)
        for idx in range(Lfo.length):
            lights[idx] = (250, 250, 255)
            if butts.pressed[idx]:
                lfos[idx].send()
                mode.become_normal()

        if butts.pressed[0xF]:
            mode.become_normal()

    elif mode.current == mode.SET_SPEED_CHOOSE_LFO:
        lights[0xF] = (255, 0, 0)
        for idx in range(Lfo.length):
            lights[idx] = (255, 255, 240)
            if butts.pressed[idx]:
                setting_lfo = lfos[idx]
                mode.become(mode.SET_SPEED)
        if butts.pressed[0xF]:
            mode.become_normal()

    elif mode.current == mode.SET_SPEED:
        lights[0xF] = (255, 0, 0)
        for idx in range(0xB):
            if idx == setting_lfo.speed:
                lights[idx] = (40, 240, 40)
            else:
                lights[idx] = (40, 140, 250)
            if butts.pressed[idx]:
                setting_lfo.speed = idx
                mode.become_normal()

        if butts.pressed[0xF]:
            mode.become_normal()

    elif mode.current == mode.SET_LIMIT_CHOOSE_LFO:
        lights[0xF] = (255, 0, 0)
        for idx in range(Lfo.length):
            lights[idx] = (250, 250, 255)
            if butts.pressed[idx]:
                setting_lfo = lfos[idx]
                mode.become(mode.SET_LIMIT_START)
        if butts.pressed[0xF]:
            mode.become_normal()

    elif mode.current == mode.SET_LIMIT_START:
        lights[0xF] = (255, 0, 0)
        for idx in range(0xB):
            if idx == setting_lfo.start:
                lights[idx] = (40, 240, 40)
            else:
                lights[idx] = (255, 200, 30)
            if butts.pressed[idx]:
                setting_lfo.start = idx
                mode.become(mode.SET_LIMIT_END)
        if butts.pressed[0xF]:
            mode.become_normal()

    elif mode.current == mode.SET_LIMIT_END:
        lights[0xF] = (255, 0, 0)
        for idx in range(setting_lfo.start, 0xB):
            if idx == setting_lfo.end:
                lights[idx] = (40, 240, 40)
            else:
                lights[idx] = (40, 230, 180)
            if butts.pressed[idx]:
                setting_lfo.end = idx
                mode.become_normal()
        if butts.pressed[0xF]:
            mode.become_normal()

    elif mode.normal:
        if butts.pressed[0xA]:
            mode.current = mode.SET_LIMIT_CHOOSE_LFO
        if butts.pressed[0xF]:
            mode.current = mode.TEACHING
        if butts.pressed[0xB]:
            mode.current = mode.SET_SPEED_CHOOSE_LFO

    lights.show()
