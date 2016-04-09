#!/usr/bin/env python

"""Captures midi from Novation Circuit.

Writes a midi file with three tracks:
- Synth 1
- Synth 2
- Drums

This can be played as-is in midi players and imported into most DAW software
for further editing.

TODO:
- Drum note presets, e.g. Bitwig Drum Machine, Tremor, Battery, Logic Drum Kit, etc.
- Optionally output multiple MIDI files to cover all drum variations (e.g. perhaps
  allow multiple format params, default = general midi)
- Add command line parameters for sounds
"""

import argparse
import mido
import os
import time

INPUT = 'Circuit'
OUTPUT_FILE = './output/capture.mid'

SONG_NAME = "Circuit Import"

TICKS_PER_BEAT = 24  # That's what Circuit uses
MAX_BARS = 8

CHANNEL_SYNTH1 = 0
CHANNEL_SYNTH2 = 1
CHANNEL_DRUMS = 9

CHANNEL_TO_INDEX = {
    CHANNEL_SYNTH1: 0,
    CHANNEL_SYNTH2: 1,
    CHANNEL_DRUMS: 2
}

# See here for other options: https://en.wikipedia.org/wiki/General_MIDI#Program_change_events
PROGRAM_SYNTH1 = 39  # Synth Bass 1
PROGRAM_SYNTH2 = 1   # Acoustic Grand Piano

# For some reason, Circuit uses drums 60-65, which mainly correspond to bongos and congas.
# We'll replace these with notes that correspond to the default Circuit drum sounds of
# kick, snare, open hi-hat, closed hi-hat respectively.
# See here for other options: https://en.wikipedia.org/wiki/General_MIDI#Percussion
DRUM_REPLACEMENTS = {
    60: 36,  # Bass Drum 1
    62: 38,  # Snare Drum 1
    64: 42,  # Closed Hi-hat (44 would be Pedal Hi-Hat)
    65: 46,  # Open Hi-hat
}

def main():
    parser = argparse.ArgumentParser(
        description="Capture MIDI from Novation Circuit and write to .mid file.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--verbose', action='store_true', help="Verbose output")
    parser.add_argument('-i', '--input', action='store', default=INPUT,
                        help="MIDI Input")
    parser.add_argument('-o', '--output', action='store', default=OUTPUT_FILE,
                        help="Output filename")
    parser.add_argument('-t', '--tempo', type=int, action='store', help="Tempo in BPM")
    parser.add_argument('-b', '--bars', type=int, action='store', default=MAX_BARS,
                        help="Max # bars (0 = until Stop)")
    args = parser.parse_args()

    output_dir = os.path.dirname(args.output)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    mido.set_backend('mido.backends.rtmidi')

    with mido.MidiFile(type=1, ticks_per_beat=TICKS_PER_BEAT) as mid:
        # Create tracks
        tempo_map_track = mid.add_track(name=SONG_NAME)
        tracks = [mid.add_track(name="Synth 1"),
            mid.add_track(name="Synth 2"),
            mid.add_track(name="Drums")]

        # Set synth instruments
        tracks[CHANNEL_SYNTH1].append(mido.Message('program_change', program=PROGRAM_SYNTH1))
        tracks[CHANNEL_SYNTH2].append(mido.Message('program_change', program=PROGRAM_SYNTH2))

        with mido.open_input(args.input) as port:
            capture = False
            final_tick = False
            # Start clocks at -1 to account for Circuit's leading clock message after start
            clocks = [-1, -1, -1]
            total_ticks = 0
            print("Push 'Play' to start capture.")

            for msg in port:
                if msg.type == 'start':
                    print("Starting capture.")
                    capture = True
                    start_time = time.time()
                elif msg.type == 'stop':
                    print("Stopping capture.")
                    capture = False
                    break
                elif capture:
                    if msg.type == 'clock':
                        clocks = [c + 1 for c in clocks]
                        total_ticks += 1
                        if args.verbose:
                            print("Ticks: %d" % total_ticks)
                        if args.bars > 0 and total_ticks > TICKS_PER_BEAT * 4 * args.bars:
                            if final_tick:
                                # We've already processed the final tick => stop
                                break
                            else:
                                final_tick = True
                                print("End of song. Stopping capture.")
                    elif msg.type in ['note_on', 'note_off']:
                        # During final tick, only accept note_off messages
                        if msg.type == 'note_off' or not final_tick:
                            index = CHANNEL_TO_INDEX[msg.channel]
                            track = tracks[index]

                            # Set message time to current clock count, then reset this track's clock
                            msg.time = clocks[index]
                            clocks[index] = 0

                            if msg.channel == CHANNEL_DRUMS:
                                msg.note = DRUM_REPLACEMENTS[msg.note]

                            print("Appending message: %s" % msg)
                            track.append(msg)

        # Figure out BPM, either from command line argument or from actual timing
        bpm = args.tempo
        if not bpm:
            end_time = time.time()
            delta = end_time - start_time
            beats = total_ticks / TICKS_PER_BEAT
            bpm = int(round(beats * 60 / delta))
        print("BPM: %d" % bpm)

        # Write tempo and time signature to tempo map track
        tempo_map_track.append(mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(bpm)))
        tempo_map_track.append(mido.MetaMessage('time_signature', numerator=4, denominator=4))

        mid.save(args.output)

    print("All done!")

#
# === Main ===
#

if __name__ == "__main__":
  main()
