import os
import time

import numpy
import pygame
import pygame.freetype
from midiutil import MIDIFile

VOLUME_MULT = 0.3
BRIGHT_RED = (255, 200, 200)
BRIGHT_GREEN = (120, 255, 120)
BRIGHT_BLUE = (120, 120, 255)
BRIGHT_PURPLE = (160, 120, 235)
BRIGHT_GRAY = (150, 150, 150)
DARK_RED = (255, 0, 0)
DARK_GREEN = (0, 120, 0)
DARK_BLUE = (33, 33, 230)
DARK_PURPLE = (40, 0, 255)
DARK_GRAY = (64, 64, 64)
WHITE = (255, 255, 255)

screen: pygame.Surface
clock: pygame.time.Clock
chord_progression: list
chord_pattern: list
bass_notes: list
bass_pattern: list
beat_pattern: list
bpm: int
beat: int = -1
cur_beat: int = -1
start_time: float
block_seq: list
blocks: list = []
font: pygame.freetype.Font


def init():
    global screen, clock, font
    pygame.init()
    screen = pygame.display.set_mode((640, 480))
    clock = pygame.time.Clock()
    pygame.mixer.init()
    pygame.mixer.Channel(0).set_volume(0.2 * VOLUME_MULT)
    pygame.mixer.Channel(1).set_volume(0.1 * VOLUME_MULT)
    pygame.mixer.Channel(2).set_volume(0.1 * VOLUME_MULT)
    pygame.mixer.Channel(3).set_volume(0.1 * VOLUME_MULT)
    pygame.mixer.Channel(4).set_volume(0.2 * VOLUME_MULT)
    pygame.mixer.Channel(5).set_volume(0.2 * VOLUME_MULT)
    font = pygame.freetype.Font('UbuntuMono-Regular.ttf', size=30, )
    screen.fill("black")


def byte_to_bools(byte):
    binary_str = f"{byte:08b}"
    return [bit == '1' for bit in binary_str]


def gen_note(note: int, duration: int):
    cycle = 44100.0 / ((2 ** (((note & 127) - 69) / 12)) * 440.0)
    arr = numpy.arange(duration * 1323000 / bpm - min(1500, 330750 // bpm))
    waveform = numpy.where(numpy.mod(arr, cycle) > cycle / 2, 32767, -32767).T.astype(numpy.int16)
    waveform = numpy.vstack((waveform, waveform)).transpose().copy(order='C')
    return pygame.sndarray.make_sound(waveform)


def simple_hash(seed):
    int_seed = numpy.uint64(seed)
    int_seed = (((int_seed >> 16) ^ int_seed) * 0x119de1f3) & 0xffffffff
    int_seed = (((int_seed >> 16) ^ int_seed) * 0x119de1f3) & 0xffffffff
    int_seed = ((int_seed >> 16) ^ int_seed)
    return int_seed & 1


def gen_noise(noise_id: int):
    cycles = [45.1584, 16.9344, 5.6448]
    cycle = cycles[noise_id]
    noise_gen = numpy.vectorize(simple_hash)
    arr = numpy.arange(661500 / bpm - min(1500, 330750 // bpm))
    waveform = numpy.where(noise_gen(arr//cycle), 32767, -32767).T.astype(numpy.int16)
    waveform = numpy.vstack((waveform, waveform)).transpose().copy(order='C')
    return pygame.sndarray.make_sound(waveform)


def play_chord(chord_id: int, duration):
    global chord_progression
    chord = chord_progression[chord_id * 3:(chord_id + 1) * 3]
    notes_list = [gen_note(i, duration) for i in chord]
    for i in range(3):
        pygame.mixer.Channel(i + 1).play(notes_list[i])


def check_on_beat():
    global beat, start_time
    tick_cycle = 30 / bpm
    if time.time() - start_time - beat * tick_cycle > tick_cycle:
        beat += 1
        return True
    return False


def note_to_y_pos(note: int):
    return 220 - ((note & 127) - 69) * 5


def format_seconds(secs: float):
    minutes = int(secs // 60)
    remaining_secs = round(secs % 60, 1)
    return f'{minutes}:{remaining_secs:04.1f}'


def render_text(text: str, coord: tuple, size: int = 30, color=WHITE, align: int = 0):
    global font
    font.size = size
    text_surf, _ = font.render(text, color)
    dx, dy = text_surf.get_rect().width, text_surf.get_rect().height
    x1, y1 = coord[0] - (dx / 2) * align, coord[1]
    screen.blit(text_surf, (x1, y1))


def render_block(blk_id: int, block_data: list):
    start_x = 0
    start_y = 0
    color: tuple = (0, 0, 0)
    dark_color: tuple = (0, 0, 0)
    start_pos = 0
    for i in range(65):
        if i == 64 or block_data[i] > 0:
            if i > 0:
                if start_pos <= cur_beat < i:
                    dark_color = color
                    color = WHITE
                pygame.draw.line(screen, dark_color, (start_x + 3, start_y), (i * 10 - 2, start_y), 5)
                pygame.draw.rect(screen, color, pygame.Rect(start_x, start_y - 2, 3, 5))
            if i < 64:
                start_y = note_to_y_pos(block_data[i])
                start_x = i * 10
                color = BRIGHT_RED if (block_data[i] & 128) > 0 else BRIGHT_GREEN
                dark_color = DARK_RED if (block_data[i] & 128) > 0 else DARK_GREEN
            start_pos = i


def render_end(start_note: int):
    start_y = note_to_y_pos(start_note)
    color = BRIGHT_RED if (start_note & 128) > 0 else BRIGHT_GREEN
    dark_color = DARK_RED if (start_note & 128) > 0 else DARK_GREEN
    if cur_beat < 8:
        dark_color = color
        color = WHITE
    pygame.draw.line(screen, dark_color, (3, start_y), (78, start_y), 5)
    pygame.draw.rect(screen, color, pygame.Rect(0, start_y - 2, 3, 5))


def render_chords():
    for i in range(8):
        x_offset = i * 80
        start_beat = i * 8
        cur_chord = chord_progression[(i & 3) * 3: (i & 3) * 3 + 3]
        for j in chord_pattern:
            for k in cur_chord:
                start_y = note_to_y_pos(k)
                dark_color = BRIGHT_BLUE if start_beat <= cur_beat < start_beat + j else DARK_BLUE
                color = WHITE if start_beat <= cur_beat < start_beat + j else BRIGHT_BLUE
                pygame.draw.line(screen, dark_color, (x_offset, start_y), (x_offset + j * 10 - 2, start_y), 5)
                pygame.draw.rect(screen, color, pygame.Rect(x_offset, start_y - 2, 3, 5))
            x_offset += j * 10
            start_beat += j



def render_bass_beat():
    for i in range(8):
        for j in range(8):
            dark_color = BRIGHT_PURPLE if ((i << 3) | j) <= cur_beat < ((i << 3) | j) + 1 else DARK_PURPLE
            color = WHITE if ((i << 3) | j) <= cur_beat < ((i << 3) | j) + 1 else BRIGHT_PURPLE
            if bass_pattern[j]:
                start_y = note_to_y_pos(bass_notes[(i&3)*3 + bass_pattern[j] - 1])
                pygame.draw.line(screen, dark_color, (i * 80 + j * 10, start_y), (i * 80 + j * 10 + 10 - 2, start_y), 5)
                pygame.draw.rect(screen, color, pygame.Rect(i * 80 + j * 10, start_y - 2, 3, 5))

            dark_color = BRIGHT_GRAY if ((i << 3) | j) <= cur_beat < ((i << 3) | j) + 1 else DARK_GRAY
            color = WHITE if ((i << 3) | j) <= cur_beat < ((i << 3) | j) + 1 else BRIGHT_GRAY
            if beat_pattern[j]:
                start_y = 90 - beat_pattern[j] * 5
                pygame.draw.line(screen, dark_color, (i * 80 + j * 10, start_y), (i * 80 + j * 10 + 5, start_y), 5)
                pygame.draw.rect(screen, color, pygame.Rect(i * 80 + j * 10, start_y - 2, 3, 5))


def render_blocks(current_block_id):
    block_amount = len(block_seq) + 2
    block_chars = ['S'] + [str(i) for i in block_seq] + ['E']
    start_x = 635 - 25 * block_amount
    for i in range(block_amount):
        bg = (60, 60, 60)
        fg = WHITE
        if i == current_block_id:
            bg = WHITE
            fg = (0, 0, 0)
        pygame.draw.rect(screen, bg, pygame.Rect(start_x + 25 * i, 41, 23, 23))
        render_text(block_chars[i], (start_x + 12 + 25 * i, 43), size=25, align=1, color=fg)


def render_screen():
    global cur_block, blocks
    render_text('RMG Music Player V2.0', (320, 5), align=1)
    screen.fill((200, 200, 200), (0, 35, 640, 2))
    cur_time = ((time.time() - start_time) * bpm / 30) % 64
    pygame.draw.line(screen, (200, 200, 200), (cur_time * 10, 75), (cur_time * 10, 440))
    render_chords()
    if cur_block > -1:
        render_text(f'Melody: Block {cur_block}', (5, 43), size=25)
        render_block(cur_block, blocks[cur_block])
    elif cur_block == -2:
        render_text(f'Melody: End', (5, 43), size=25)
        render_end(blocks[block_seq[-1]][0])
    else:
        render_text(f'Melody: Start', (5, 43), size=25)
    render_blocks(beat >> 6)
    render_bass_beat()
    screen.fill((127, 127, 127), (0, 70, 640, 2))
    screen.fill((127, 127, 127), (0, 443, 640, 2))
    render_text(f'{format_seconds(time.time() - start_time)}/{format_seconds(((len(block_seq) + 2) << 6) * 30 / bpm)}',
                (635, 450), align=2)
    render_text(f'FPS:{round(clock.get_fps(), 1)}', (5, 450))


try:
    init()
    cur_block = -1
    with open('notes.bin', "rb") as file:
        bpm = ord(file.read(1))
        chord_progression = list(file.read(12))
        tmp_pattern = byte_to_bools(ord(file.read(1)))
        chord_pattern = []
        tmp_prev = 0
        for i in range(9):
            if i == 8 or (0 < i < 8 and tmp_pattern[i]):
                chord_pattern.append(i - tmp_prev)
                tmp_prev = i
        bass_notes = list(file.read(12))
        tmp_bytes = list(file.read(2))
        bass_pattern = [(tmp_bytes[i]&(192>>(j<<1)))>>(((~j)&3)<<1) for i in range(2) for j in range(4)]
        tmp_bytes = list(file.read(2))
        beat_pattern = [(tmp_bytes[i]&(192>>(j<<1)))>>(((~j)&3)<<1) for i in range(2) for j in range(4)]
        block_seq = []
        while True:
            tmp_prev = ord(file.read(1))
            if tmp_prev == 0:
                break
            block_seq.append(tmp_prev - 1)
        for i in range(5):
            blocks.append(list(file.read(64)))
        start_time = time.time()

        os.makedirs('midi_output', exist_ok=True)

        track = 0
        for i in range(len(blocks)):
            temp_midi = MIDIFile(1)
            temp_midi.addTempo(track, 0, bpm)
            prev_time = -1.0
            prev_note = -1
            for j in range(len(blocks[i])):
                if blocks[i][j] > 0:
                    if prev_time >= 0.0:
                        temp_midi.addNote(track, 0, prev_note, prev_time, j / 2 - prev_time, 64)
                    prev_time = j / 2
                    prev_note = blocks[i][j] & 127
            if prev_time >= 0.0:
                temp_midi.addNote(track, 0, prev_note, prev_time, len(blocks[i]) / 2 - prev_time, 64)
            with open(f"midi_output/block{i}.mid", 'wb') as output_file:
                temp_midi.writeFile(output_file)

        temp_midi = MIDIFile(3)
        for track in range(3):
            temp_midi.addTempo(track, 0, bpm)
            for i in range(4):
                cur_chord_time = 0
                for j in chord_pattern:
                    temp_midi.addNote(track, 0, chord_progression[i*3+track], i*4.0 + cur_chord_time/2, j/2, 64)
                    temp_midi.addNote(track, 0, chord_progression[i*3+track], 16 + i*4.0 + cur_chord_time/2, j/2, 64)
                    cur_chord_time += j
        with open(f"midi_output/chords.mid", 'wb') as output_file:
            temp_midi.writeFile(output_file)


        running = True
        chord_time = 0
        pattern_id = 0
        while running:
            cur_beat = beat & 63
            if check_on_beat():
                tmp_cur_beat = beat & 63
                if beat_pattern[tmp_cur_beat&7] > 0:
                    pygame.mixer.Channel(4).play(gen_noise(beat_pattern[tmp_cur_beat&7]-1))
                if bass_pattern[tmp_cur_beat&7] > 0:
                    pygame.mixer.Channel(5).play(gen_note(bass_notes[((tmp_cur_beat >> 3) & 3) * 3 + bass_pattern[tmp_cur_beat&7] - 1], 1))
                if beat >= chord_time:
                    if chord_time & 7 == 0:
                        pattern_id = 0
                    else:
                        pattern_id += 1
                    chord_time += chord_pattern[pattern_id]
                    play_chord((beat >> 3) & 3, chord_pattern[pattern_id])
                if 64 <= beat < ((len(block_seq) + 1) << 6):
                    cur_block = block_seq[(beat - 64) >> 6]
                    length = 1
                    cur_note = blocks[cur_block][tmp_cur_beat]
                    if cur_note > 0:
                        tmp_cur_beat += 1
                        while tmp_cur_beat < 64 and blocks[cur_block][tmp_cur_beat] == 0:
                            tmp_cur_beat += 1
                            length += 1
                        pygame.mixer.Channel(0).play(gen_note(cur_note, length))
                if beat == ((len(block_seq) + 1) << 6):
                    pygame.mixer.Channel(0).play(gen_note(blocks[block_seq[-1]][0], 8))
                    cur_block = -2
                if beat >= ((len(block_seq) + 2) << 6):
                    break
            screen.fill((0, 0, 0))
            render_screen()
            pygame.display.flip()
            clock.tick()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
except Exception as E:
    print(E)
