# Source: https://github.com/pygame/pygame/blob/main/examples/audiocapture.py
import json
import pygame as pg
import time
import numpy as np
from scipy.io.wavfile import write
import sys
from pygame._sdl2 import (
    get_audio_device_names,
    AudioDevice,
    AUDIO_S16,
    AUDIO_ALLOW_FORMAT_CHANGE,
)
import pygame_widgets
from pygame_widgets.dropdown import Dropdown

# Default parameters
config_filename = "config.json"
default_chunk_rate = 50
default_sample_rate = 44100
default_margin = 0.25
default_threshold = 200
default_mic_index = 0
default_screen_width = 1000
default_screen_height = 600

def read_config():
    try:
        with open(config_filename, 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        # If file is not found, create it with default parameters
        print("Warning: no config.json found, creating one using default values")
        config = {
            'CHUNK_RATE': default_chunk_rate,
            'SAMPLE_RATE': default_sample_rate,
            'MARGIN': default_margin,
            'THRESHOLD': default_threshold,
            'MIC_INDEX': default_mic_index,
            "SCREEN_WIDTH": default_screen_width,
            "SCREEN_HEIGHT": default_screen_height
        }
        with open(config_filename, 'w') as f:
            json.dump(config, f, indent=4)
    
    return config

config = read_config()

def update_config(kwargs):
    global config
    for key, value in kwargs.items():
        config[key] = value
    with open(config_filename, 'w') as f:
        json.dump(config, f, indent=4)

m = int(config['MARGIN']*config['CHUNK_RATE'])
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
else:
    print("No transcript file given.")
    print("Usage: python recordTrimEdit.py transcript.txt [output.wav]")
    sys.exit(1)
destination = "output.wav"
if len(sys.argv) >= 3:
    destination = sys.argv[2]


pg.mixer.pre_init(config['SAMPLE_RATE'], 32, 1, config['SAMPLE_RATE']//config['CHUNK_RATE'])
pg.init()

# init_subsystem(INIT_AUDIO)
names = get_audio_device_names(True)
if config['MIC_INDEX'] >= len(names):
    update_config({'MIC_INDEX': 0})

sounds = []
sound_chunks = []

audio = AudioDevice(
    devicename=names[config['MIC_INDEX']],
    iscapture=True,
    frequency=config['SAMPLE_RATE'],
    audioformat=AUDIO_S16,
    numchannels=1,
    chunksize=config['SAMPLE_RATE']//config['CHUNK_RATE'],

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
    while loudness_bytes(sound_chunks[start_pointer]) <= config['THRESHOLD'] and start_pointer < len(sound_chunks)-1:
        start_pointer += 1
    end_pointer = max(0, len(sound_chunks)-m)
    while loudness_bytes(sound_chunks[end_pointer-1]) <= config['THRESHOLD'] and end_pointer >= 1:
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
    write(filename, config['SAMPLE_RATE'], scaled)

def drawBackground(screen):
    screen.fill((255, 255, 255))

def drawWaveforms(screen):
    k = 0
    start_pointer, end_pointer = getEdges()

    if listening:
        age = (time.time()-listening_timestamp)*config['CHUNK_RATE']

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
                COLOR = [20,140,255]
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

        pg.draw.rect(screen, COLOR, pg.Rect(i+x_offset, (config["SCREEN_HEIGHT"]/2)-h/2, 1, h))

def drawTranscript(screen):
    for y in range(-2,3):
        stri = "-"
        line = y+len(keyframes)-1
        if line >= 0 and line < len(transcript):
            stri = transcript[line]

        y_start = config["SCREEN_HEIGHT"] * 0.8

        if y == 0:
            pg.draw.rect(screen, (255,255,0), pg.Rect(20,y_start,config["SCREEN_WIDTH"]-40,30))
        text_surface = my_font.render(stri, True, (0, 0, 0))
        screen.blit(text_surface, (40,y_start+y*30))

    infos = [["Left: reject snippet", "Down: listen to snippet", "Right: approve snippet"],["Enter: Instantly save (at the end)", "Left-left: Delete previous snippet","Left-down: Listen to previous snippet"],["Writing to "+destination,"",""]]
    xs = [20,280,650]
    for i in range(len(infos)):
        for j in range(len(infos[i])):
            text_surface = small_font.render(infos[i][j], True, (0, 0, 0))
            screen.blit(text_surface, (xs[i],12+22*j))

def stopListening():
    global listening
    global sound
    listening = False
    if sound is not None:
        sound.set_volume(0.0)

screen = pg.display.set_mode([config['SCREEN_WIDTH'], config['SCREEN_HEIGHT']])
my_font = pg.font.SysFont('Arial', 26)
small_font = pg.font.SysFont('Arial', 20)
sound = None
# Run until the user asks to quit
running = True

def update_audio_device(*args):
    global dropdown
    global audio
    global config

    if dropdown.getSelected() is None or dropdown.getSelected() == config['MIC_INDEX']:
        return

    print("Update")
    update_config({'MIC_INDEX': dropdown.getSelected()})
    audio.pause(1)
    audio.close()
    audio = AudioDevice(
        devicename=names[config['MIC_INDEX']],
        iscapture=True,
        frequency=config['SAMPLE_RATE'],
        audioformat=AUDIO_S16,
        numchannels=1,
        chunksize=config['SAMPLE_RATE']//config['CHUNK_RATE'],
        allowed_changes=AUDIO_ALLOW_FORMAT_CHANGE,
        callback=callback,
    )
    audio.pause(0)

dropdown = Dropdown(
    screen,
    650, 45, 300, 25,
    name='Select Audio Device',
    choices=names,
    borderRadius=3,
    colour=pg.Color(208, 208, 208),
    values=range(len(names)),
    direction='down',
    textHAlign='left'
)


while running:
    # Did the user click the window close button?
    events = pg.event.get()
    for event in events:
        if event.type == pg.QUIT:
            running = False

        if event.type == pg.KEYDOWN:
            if event.key == keys[0]: # reject audio
                stopListening()
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
                stopListening()
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
    dropdown.draw()
    update_audio_device()

    pygame_widgets.update(events)
    pg.display.flip()

chunk_size = config['SAMPLE_RATE']//config['CHUNK_RATE']

FULL_LEN = len(sound_chunks)*chunk_size
audio_full = np.zeros((FULL_LEN))
for i in range(len(sound_chunks)):
    audio_full[i*chunk_size:i*chunk_size+chunk_size] = np.frombuffer(sound_chunks[i], dtype=np.int16)
saveWav(destination,audio_full)
