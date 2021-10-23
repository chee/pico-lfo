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
oled = adafruit_ssd1306.SSD1306_I2C(oled_width, oled_height, i2c)
oled.fill(0)
oled.show()


class LFO_STATE:
    off = 0
    slow = 1
    fast = 2


# todo make Lfo class that keeps all this info together
# possibly extend from Pad class
num_lfos = 8
lfo_states = [LFO_STATE.off] * num_lfos
lfo_values = [0.0] * num_lfos
lfo_dirs = [1] * num_lfos


def lfo_line(lfo_num, lfo_val):
    line_height = oled_height // num_lfos
    # TODO consider removing gap
    oled.fill_rect(
        0,
        lfo_num * line_height,
        int(lfo_val * oled_width),
        line_height - 1,
        1,
    )


held = [False] * 16
mode = 0
tick = 0


lfo_incs = {LFO_STATE.off: 0, LFO_STATE.slow: 0.01, LFO_STATE.fast: 0.1}


bpm_mode = False
bpm = 128


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


def inc_lfo(idx, state):
    val = lfo_values[idx]
    inc = lfo_incs[state]
    dire = lfo_dirs[idx]
    lfo_values[idx] += inc * dire
    if val >= 1.0:
        lfo_dirs[idx] = -1
    elif val <= 0:
        lfo_dirs[idx] = 1


while True:
    # todo use bpm
    time.sleep(0.01)
    oled.fill(0)
    # todo set bpm mode (press B then type a number then press F to select. press B again to cancel)
    # todo set channel mode (press C, type number to set midi channel, then F to select. press B to cancel)
    # in bpm and channel mode: numbers should be white, B should be red and F should be green
    # todo teaching mode (hold F, disables LFO, lets you teach cc to machine)
    # todo set limits mode (press A, press a control, press a number and then select start (0-A) and end (0-A))

    for idx, state in enumerate(lfo_states):
        inc_lfo(idx, state)
        val = lfo_values[idx]
        if val < 0:
            val = 0
        if val > 1:
            val = 1
        col_offset = int(128 * val)
        if state == LFO_STATE.off:
            lights[idx] = (0, 0, 0)
        elif state == LFO_STATE.slow:
            lights[idx] = (255, col_offset, 0)
        elif state == LFO_STATE.fast:
            lights[idx] = (0, col_offset, 255)

        if state != LFO_STATE.off:
            midi.send(ControlChange(idx, int(val * 127)))

        lfo_line(idx, val)

    for idx, pressed in enumerate(read_butts()):
        if pressed and not held[idx]:
            if idx <= num_lfos:
                if lfo_states[idx] == LFO_STATE.off:
                    lfo_states[idx] = LFO_STATE.slow
                elif lfo_states[idx] == LFO_STATE.slow:
                    lfo_states[idx] = LFO_STATE.fast
                elif lfo_states[idx] == LFO_STATE.fast:
                    lfo_states[idx] = LFO_STATE.off
                pass
            # todo initiate BPM mode (so this is holding B and typing a number)
            held[idx] = True
        elif pressed and held[idx]:
            # todo BPM mode (take another number)
            pass
        elif not pressed and held[idx]:
            # todo BPM mode (set bpm)
            held[idx] = False
    oled.show()
    lights.show()
