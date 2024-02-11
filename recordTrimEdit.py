# Source: https://github.com/pygame/pygame/blob/main/examples/audiocapture.py

import pygame as pg
import time
import io
import soundfile as sf
import numpy as np
from scipy.io.wavfile import read, write
import sys
from pygame._sdl2 import (
    get_audio_device_names,
    AudioDevice,
    AUDIO_S16,
    AUDIO_ALLOW_FORMAT_CHANGE,
)
from pygame._sdl2.mixer import set_post_mix

CHUNK_RATE = 50
SAMPLE_RATE = 44100
CHUNK_SIZE = SAMPLE_RATE//CHUNK_RATE
MARGIN = 0.25 # length of wiggle room at the start and end of sections that is not included (e.g. keyboard tapping sounds)
THRESHOLD = 200
m = int(MARGIN*CHUNK_RATE)
keys = [pg.K_LEFT, pg.K_DOWN, pg.K_RIGHT, pg.K_RETURN]
# reject, listen, approve, instant save .wav file

listening = False
listening_timestamp = 0
listening_edges = None
def callback(audiodevice, audiomemoryview):
    """This is called in the sound thread.

    Note, that the frequency and such you request may not be what you get.
    """
    global listening
    if not listening:
        sound_chunks.append(bytes(audiomemoryview))

transcript = []
if len(sys.argv) >= 2:
    filename = sys.argv[1]
    f = open(filename,"r+",encoding="utf-8")
    transcript = f.read().split("\n")
    f.close()
destination = "output.wav"
if len(sys.argv) >= 3:
    destination = sys.argv[2]


pg.mixer.pre_init(SAMPLE_RATE, 32, 1, CHUNK_SIZE)
pg.init()

# init_subsystem(INIT_AUDIO)
names = get_audio_device_names(True)
mic_index = 1 #int(input(f"Which microphone to use? (index): {names}\n"))

sounds = []
sound_chunks = []

audio = AudioDevice(
    devicename=names[mic_index],
    iscapture=True,
    frequency=SAMPLE_RATE,
    audioformat=AUDIO_S16,
    numchannels=1,
    chunksize=CHUNK_SIZE,

    allowed_changes=AUDIO_ALLOW_FORMAT_CHANGE,
    callback=callback,
)

# start recording.
keyframes = [0]
audio.pause(0)

def loudness_bytes(chunk):
    return loudness(np.frombuffer(chunk, dtype=np.int16))

def loudness(arr):
    return np.max(np.abs(arr))

def getEdges():
    if len(sound_chunks) == 0:
        return 0,0

    start_pointer = min(len(sound_chunks)-1, keyframes[-1]+m)
    while loudness_bytes(sound_chunks[start_pointer]) <= THRESHOLD and start_pointer < len(sound_chunks)-1:
        start_pointer += 1
    end_pointer = max(0, len(sound_chunks)-m)
    while loudness_bytes(sound_chunks[end_pointer-1]) <= THRESHOLD and end_pointer >= 1:
        end_pointer -= 1

    start_pointer = max(keyframes[-1],start_pointer-m)
    end_pointer = min(len(sound_chunks),end_pointer+m)
    if start_pointer > end_pointer:
        start_pointer = end_pointer
    return start_pointer, end_pointer

def removeSilentEnds():
    global sound_chunks
    global keyframes

    start_pointer, end_pointer = getEdges()

    sound_chunks_p1 = sound_chunks[0:keyframes[-1]]
    sound_chunks_p2 = sound_chunks[start_pointer:end_pointer]
    sound_chunks = sound_chunks_p1 + sound_chunks_p2

def saveWav(filename,audio):
    scaled = np.int16(audio / np.max(np.abs(audio)) * 32767)
    write(filename, SAMPLE_RATE, scaled)

def drawBackground(screen):
    screen.fill((255, 255, 255))

def drawWaveforms(screen):
    k = 0
    start_pointer, end_pointer = getEdges()

    if listening:
        age = (time.time()-listening_timestamp)*CHUNK_RATE

    x_offset = min(0,940-len(sound_chunks))
    for i in range(len(sound_chunks)):
        chunk = sound_chunks[i]

        audio_array = np.frombuffer(chunk, dtype=np.int16)
        audio_array.reshape((882))
        h = np.amax(np.abs(audio_array))*0.07

        if k < len(keyframes) and i >= keyframes[k]:
            pg.draw.rect(screen, (128,128,128), pg.Rect(i+x_offset, 0, 1, 600))
            k += 1

        if k >= len(keyframes):
            COLOR = [0,0,0]
            if listening and i-listening_edges[0] < age:
                COLOR = [0,128,255]
            if i >= len(sound_chunks)-m:
                COLOR = [255,0,0]
            if i < start_pointer or i >= end_pointer:
                COLOR = [190,190,190]
            if (i >= keyframes[-1] and i < keyframes[-1]+m):
                COLOR = [190,190,190]
        else:
            if k%2 == 0:
                COLOR = [0,170,0]
            else:
                COLOR = [170,170,0]

        pg.draw.rect(screen, COLOR, pg.Rect(i+x_offset, 260-h/2, 1, h))

def drawTranscript(screen):
    for y in range(-2,3):
        stri = "-"
        line = y+len(keyframes)-1
        if line >= 0 and line < len(transcript):
            stri = transcript[line]

        if y == 0:
            pg.draw.rect(screen, (255,255,0), pg.Rect(20,480,1000,30))
        text_surface = my_font.render(stri, False, (0, 0, 0))
        screen.blit(text_surface, (40,480+y*30))

    infos = [["Left: reject snippet", "Down: listen to snippet", "Right: approve snippet"],["Enter: Instantly save (at the end)", "Left-left: Delete previous snippet","Left-down: Listen to previous snippet"],["Writing to "+destination,"",""]]
    for i in range(len(infos)):
        for j in range(len(infos[i])):
            text_surface = small_font.render(infos[i][j], False, (0, 0, 0))
            screen.blit(text_surface, (30+300*i,15+18*j))


screen = pg.display.set_mode([1000, 600])
my_font = pg.font.SysFont('Arial', 26)
small_font = pg.font.SysFont('Arial', 16)
sound = None
# Run until the user asks to quit
running = True
while running:
    # Did the user click the window close button?
    for event in pg.event.get():
        if event.type == pg.QUIT:
            running = False

        if event.type == pg.KEYDOWN:
            if event.key == keys[0]: # reject audio
                listening = False
                sound.set_volume(0.0)
                if len(keyframes) >= 2 and keyframes[-1] >= len(sound_chunks)-m:
                    keyframes.pop()
                sound_chunks = sound_chunks[0:keyframes[-1]]

            if event.key == keys[1]: # listen to audio
                if len(keyframes) >= 2 and keyframes[-1] >= len(sound_chunks)-m:
                    keyframes.pop()
                listening_edges = getEdges()
                if listening_edges[1] > listening_edges[0]:
                    listening = True

                    audio_temp = np.zeros((0))
                    for i in range(listening_edges[0],listening_edges[1]):
                        audio_temp = np.append(audio_temp,np.frombuffer(sound_chunks[i], dtype=np.int16))
                    saveWav("temp.wav",audio_temp)

                    listening_timestamp = time.time()
                    sound = pg.mixer.Sound("temp.wav")
                    sound.play()
                    sound.set_volume(1.0)

            if event.key == keys[2]: # approve audio
                listening = False
                sound.set_volume(0.0)
                removeSilentEnds()
                keyframes.append(int(len(sound_chunks)))
                if len(keyframes) >= len(transcript):
                    running = False

            if event.key == keys[3]: # instant save
                listening = False
                removeSilentEnds()
                running = False

    # Fill the background with white
    drawBackground(screen)
    drawWaveforms(screen)
    drawTranscript(screen)
    pg.display.flip()

audio_full = np.zeros((0))
for chunk in sound_chunks:
    audio_full = np.append(audio_full,np.frombuffer(chunk, dtype=np.int16))

saveWav(destination,audio_full)
