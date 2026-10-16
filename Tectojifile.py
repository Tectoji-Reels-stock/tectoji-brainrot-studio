#!/usr/bin/env python3
"""Tectoji Brainrot Studio - Stage 1: one complete sample Short, fully offline.
Script -> voice (espeak-ng) -> animation (Pillow) -> captions -> music/SFX (numpy) -> MP4 (FFmpeg).
Usage: python tectoji.py [--seed N] [--out out]
"""
import argparse, hashlib, json, math, os, random, shutil, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H, FPS, SR = 1080, 1920, 24, 44100
MIN_S, MAX_S = 20.0, 35.0

# ---------------------------------------------------------------- content
CHARS = [("Sir Banana", "🍌"), ("Captain Toaster", "🍞"), ("Mr Sock", "🧦"),
         ("Lady Cactus", "🌵"), ("Professor Cheese", "🧀"), ("Duke Meatball", "🍝"),
         ("Baby Ghost", "👻"), ("Chef Pickle", "🥒"), ("Agent Potato", "🥔"),
         ("Queen Donut", "🍩"), ("Uncle Moon", "🌝"), ("Doctor Frog", "🐸")]
OBJS = [("glowing spoon", "🥄"), ("haunted calculator", "🧮"), ("suspicious umbrella", "☂️"),
        ("talking crayon", "🖍️"), ("forbidden bucket", "🪣"), ("shiny rock", "🪨"),
        ("angry clock", "⏰"), ("mystery key", "🔑"), ("sleepy rocket", "🚀"),
        ("golden sandwich", "🥪"), ("cursed balloon", "🎈"), ("lonely magnet", "🧲")]
PLACES = ["the school canteen", "a parking lot", "the moon", "a bus stop at 3 AM",
          "grandma's wifi router", "the cheese museum", "a very small elevator",
          "the last row of a cinema", "a bowl of soup"]
STATES = ["speaking only in compliments", "walking backwards", "allergic to Tuesdays",
          "covered in glitter", "afraid of the number seven", "singing in slow motion",
          "wearing three hats", "completely invisible on Mondays"]
FIXES = ["a loud whistle", "interpretive dancing", "a strongly worded letter",
         "two spoons and hope", "a mysterious sandwich", "pure confidence"]
RELS = ["grandfather", "landlord", "future self", "biggest fan", "evil twin", "math teacher"]

HOOKS = ["Nobody warned {A} about the {O}.", "{A} found a {O} in {P}. Big mistake.",
         "POV: {A} just woke up next to a {O}.", "This is the day {A} lost to a {O}.",
         "Stop scrolling. {A} has a {O}.", "{A} swore never to touch the {O} again."]
SETUPS = ["It started in {P}. {B} said, do not open it. {A} opened it.",
          "{B} warned everyone. Nobody listened, especially {A}.",
          "Everything was normal until the {O} blinked."]
ESCALATE = ["Then the {O} began speaking in wifi signals.", "{B} screamed, but only in lowercase.",
            "The sky turned the color of burnt toast.", "Suddenly, every clock showed banana o'clock.",
            "A crowd of pigeons arrived wearing tiny ties."]
CHAOS = ["{A} tried to fix it with {F}. It got worse.", "{B} tried {F}. The {O} laughed.",
         "Everyone panicked and started {S}."]
TWISTS = ["Then everyone was {S}. Nobody knows why.", "The whole town became {S} overnight.",
          "And that's how {A} ended up {S}."]
PUNCH = ["Turns out the {O} was {A}'s {R} all along.", "The {O} was just {B}'s {R} in disguise.",
         "Plot twist: {A} was the {O} the whole time."]
