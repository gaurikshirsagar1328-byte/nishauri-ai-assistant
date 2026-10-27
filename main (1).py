import tkinter as tk
from tkinter import scrolledtext
import threading
import speech_recognition as sr
import pyttsx3
import webbrowser
import requests
import pyautogui
import subprocess
import re
import random
import math
import ctypes
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
from datetime import datetime
from threading import Lock

# =========================================================
# NISHAURI AI ASSISTANT - Animated GUI + Voice Commands
# Works with Python 3.10+ on Windows
# =========================================================

APP_NAME = "Nishauri"
SHUTDOWN_DELAY = 60

engine = pyttsx3.init()
engine.setProperty("rate", 175)
engine.setProperty("volume", 1.0)
speech_lock = Lock()
action_lock = Lock()

pending_action = None
last_url = None
is_listening = False
is_speaking = False
animation_mode = "idle"
animation_phase = 0
particles = []
orb_size = 88


def log_message(sender, message):
    def update():
        chat_box.configure(state="normal")
        chat_box.insert(tk.END, f"{sender}: {message}\n\n")
        chat_box.see(tk.END)
        chat_box.configure(state="disabled")
    try:
        root.after(0, update)
    except tk.TclError:
        pass


def set_status(message, mode=None):
    def update():
        status_label.config(text=message)
        if mode:
            global animation_mode
            animation_mode = mode
    try:
        root.after(0, update)
    except tk.TclError:
        pass


def speak(text):
    global is_speaking, animation_mode
    log_message(APP_NAME, text)
    is_speaking = True
    set_status("Nishauri is responding…", "speaking")

    def say():
        global is_speaking, animation_mode
        with speech_lock:
            try:
                engine.say(text)
                engine.runAndWait()
            except Exception as error:
                print("Speech error:", error)
            finally:
                is_speaking = False
                animation_mode = "heard"
                set_status("Command complete ✨", "heard")
    threading.Thread(target=say, daemon=True).start()


# ------------------ Magical orb animation ------------------

def draw_orb():
    global animation_phase, particles

    canvas.delete("all")
    width = max(canvas.winfo_width(), 360)
    height = max(canvas.winfo_height(), 210)
    cx, cy = width / 2, height / 2 - 2
    animation_phase += 0.07

    mode = animation_mode
    if mode == "listening":
        core = "#46E8FF"
        glow = "#178BFF"
        label = "LISTENING"
        pulse = 13
    elif mode == "speaking":
        core = "#E5A7FF"
        glow = "#9B5CFF"
        label = "NISHAURI IS SPEAKING"
        pulse = 10
    elif mode == "heard":
        core = "#72FFD6"
        glow = "#21C99A"
        label = "COMMAND RECEIVED"
        pulse = 5
    else:
        core = "#8DA9FF"
        glow = "#5A62FF"
        label = "READY FOR MAGIC"
        pulse = 7

    radius = orb_size + math.sin(animation_phase * 2) * pulse

    # Soft concentric glow rings
    for i in range(7, 0, -1):
        r = radius + i * 9 + math.sin(animation_phase + i) * 2
        canvas.create_oval(
            cx-r, cy-r, cx+r, cy+r,
            outline=glow, width=1
        )

    # Orb body
    canvas.create_oval(
        cx-radius, cy-radius, cx+radius, cy+radius,
        fill="#18264A", outline=core, width=3
    )
    inner = radius * 0.68
    canvas.create_oval(
        cx-inner, cy-inner, cx+inner, cy+inner,
        fill="#263A77", outline=core, width=2
    )
    small = radius * 0.34
    canvas.create_oval(
        cx-small, cy-small, cx+small, cy+small,
        fill=core, outline="#FFFFFF", width=1
    )

    # Sparkles orbiting the orb while listening / responding
    sparkle_count = 22 if mode in ("listening", "speaking") else 12
    for i in range(sparkle_count):
        angle = animation_phase * (1.35 if mode == "listening" else 0.75) + (
            2 * math.pi * i / sparkle_count
        )
        orbit = radius + 27 + 10 * math.sin(animation_phase * 1.7 + i)
        x = cx + math.cos(angle) * orbit
        y = cy + math.sin(angle) * orbit * 0.68
        s = 2 + (i % 3)
        canvas.create_oval(x-s, y-s, x+s, y+s, fill=core, outline="")

    # Tiny floating stars
    random.seed(11)
    for i in range(18):
        x = (i * 79 + animation_phase * 24) % width
        y = (i * 43 + math.sin(animation_phase + i) * 13) % height
        canvas.create_text(x, y, text="✦", fill="#5267A8",
                          font=("Segoe UI", 8 + (i % 4)))

    canvas.create_text(
        cx, cy + radius + 36, text=label,
        fill=core, font=("Segoe UI", 10, "bold")
    )
    canvas.after(45, draw_orb)


# ------------------ Speech recognition ------------------

continuous_listening = False


def listen_loop():
    """Keep listening until the user switches continuous listening off."""
    global is_listening, animation_mode, continuous_listening
    recognizer = sr.Recognizer()

    try:
        with sr.Microphone() as source:
            log_message("System", "Continuous listening is on. Say a command whenever you are ready.")
            recognizer.adjust_for_ambient_noise(source, duration=0.5)

            while continuous_listening:
                # Do not record Nishauri's own spoken response.
                while is_speaking and continuous_listening:
                    threading.Event().wait(0.1)

                if not continuous_listening:
                    break

                is_listening = True
                set_status("Listening… speak now", "listening")
                try:
                    audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
                except sr.WaitTimeoutError:
                    # Silence is normal in continuous mode; simply keep waiting.
                    continue

                if not continuous_listening:
                    break

                set_status("Processing your words…", "heard")
                try:
                    command = recognizer.recognize_google(audio, language="en-IN")
                    log_message("You", command)
                    process_command(command)
                except sr.UnknownValueError:
                    set_status("I didn't catch that — listening again ✨", "idle")
                except sr.RequestError:
                    speak("Speech recognition needs an internet connection.")
                    # Avoid repeatedly sending requests while offline.
                    while is_speaking:
                        threading.Event().wait(0.1)
                    threading.Event().wait(1.0)

                # Give the response time to finish before opening the microphone again.
                while is_speaking and continuous_listening:
                    threading.Event().wait(0.1)

                is_listening = False
                if continuous_listening:
                    set_status("Ready for your next command ✨", "idle")
                    threading.Event().wait(0.35)

    except Exception as error:
        print("Microphone error:", error)
        log_message("System", "Could not access the microphone. Check Windows microphone permissions.")
        set_status("Microphone unavailable", "idle")
    finally:
        is_listening = False
        continuous_listening = False
        try:
            root.after(0, lambda: mic_button.config(text="🎙  Start continuous listening"))
            root.after(0, lambda: set_status("Listening is off. Click the microphone to start ✨", "idle"))
        except tk.TclError:
            pass


def start_listening():
    """Toggle hands-free continuous listening on or off."""
    global continuous_listening
    if continuous_listening:
        continuous_listening = False
        set_status("Turning listening off…", "idle")
        mic_button.config(text="🎙  Start continuous listening")
        log_message("System", "Continuous listening switched off.")
        return

    continuous_listening = True
    mic_button.config(text="⏹  Stop continuous listening")
    set_status("Starting microphone…", "listening")
    threading.Thread(target=listen_loop, daemon=True).start()


# ------------------ Webpage reader ------------------

def read_webpage():
    global last_url
    if not last_url:
        speak("Please open a website or search for something first.")
        return
    try:
        set_status("Reading webpage…", "speaking")
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(last_url, headers=headers, timeout=12)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header",
                         "noscript", "svg", "form"]):
            tag.decompose()

        title = soup.title.get_text(" ", strip=True) if soup.title else "Webpage"
        parts = [
            element.get_text(" ", strip=True)
            for element in soup.find_all(["p", "h1", "h2", "h3", "li"])
        ]
        page_text = re.sub(r"\s+", " ", " ".join(p for p in parts if p)).strip()
        if not page_text:
            speak("I could not find readable text on this webpage.")
            return

        words = page_text.split()
        excerpt = " ".join(words[:180])
        speak(f"The webpage title is {title}. Here is the available text. {excerpt}")
        if len(words) > 180:
            speak("I read the first 180 words.")
    except requests.exceptions.RequestException:
        speak("I could not access that page. It may require login or block automatic reading.")
    except Exception as error:
        speak("Sorry, I could not read this webpage.")
        print("Page reading error:", error)


# ------------------ General questions / web answers ------------------

def answer_general_question(question):
    """Try a concise online answer; if unavailable, open relevant search results."""
    global last_url
    clean_question = question.strip().rstrip("?.! ")
    if not clean_question:
        speak("Please ask me a question or tell me what you would like me to do.")
        return

    set_status("Finding an answer online…", "speaking")
    headers = {"User-Agent": "NishauriAssistant/1.0 (personal desktop assistant)"}
    # Wikipedia's summary API works well for people, places, concepts and definitions.
    try:
        search_url = "https://en.wikipedia.org/w/api.php"
        search_response = requests.get(
            search_url,
            params={"action": "query", "list": "search", "srsearch": clean_question,
                    "format": "json", "srlimit": 1},
            headers=headers, timeout=6
        )
        search_response.raise_for_status()
        results = search_response.json().get("query", {}).get("search", [])
        if results:
            title = results[0].get("title", "")
            summary_url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + quote_plus(title.replace(" ", "_"))
            summary_response = requests.get(summary_url, headers=headers, timeout=6)
            if summary_response.ok:
                data = summary_response.json()
                extract = re.sub(r"\s+", " ", data.get("extract", "")).strip()
                if extract:
                    last_url = data.get("content_urls", {}).get("desktop", {}).get("page", summary_url)
                    speak(extract[:650])
                    return
    except (requests.exceptions.RequestException, ValueError, KeyError) as error:
        print("Online answer lookup:", error)

    # Search is the fallback rather than claiming that the command is unknown.
    last_url = "https://www.google.com/search?q=" + quote_plus(clean_question)
    webbrowser.open_new_tab(last_url)
    speak("I could not find a short answer to that, so I opened Google search results for " + clean_question + ".")


def close_browser_tab():
    """Bring a visible browser window forward, then close its active tab."""
    try:
        if __import__("sys").platform == "win32":
            user32 = ctypes.windll.user32
            matches = []
            EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

            def collect(hwnd, _):
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    title_buffer = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, title_buffer, length + 1)
                    title = title_buffer.value.lower()
                    if any(name in title for name in ("chrome", "edge", "firefox", "brave", "opera")):
                        matches.append(hwnd)
                return True

            user32.EnumWindows(EnumWindowsProc(collect), 0)
            if matches:
                user32.ShowWindow(matches[0], 9)  # SW_RESTORE
                user32.SetForegroundWindow(matches[0])
                threading.Event().wait(0.35)
            else:
                speak("I could not find an open browser window to close.")
                return
        pyautogui.hotkey("ctrl", "w")
        speak("Closing the active browser tab.")
    except Exception as error:
        print("Close tab error:", error)
        speak("I could not close the browser tab automatically. Please switch to the browser and press Control and W.")


# ------------------ Command processor ------------------

def process_command(command):
    global pending_action, last_url
    command = command.lower().strip()
    command = re.sub(r"[.!?,]+", "", command)

    if not command:
        return

    if command in ("help", "show commands", "what can you do"):
        speak("You can say: open YouTube, open Google, search for AI internships, play a song, "
              "what is machine learning, who is A P J Abdul Kalam, tell me the time, tell me the date, "
              "read page, close tab, close YouTube, shutdown, or exit. I can answer some general questions online too.")
        return

    if command in ("your name", "what is your name", "who are you",
                   "what's your name", "introduce yourself"):
        speak("My name is Nishauri. I am your personal AI assistant.")
        return

    if command in ("cancel", "cancel action"):
        with action_lock:
            had_action = pending_action is not None
            pending_action = None
        speak("Action cancelled." if had_action else "There is no pending action.")
        return

    if "cancel shutdown" in command:
        result = subprocess.run(["shutdown", "/a"], capture_output=True,
                                text=True, shell=False)
        if result.returncode == 0:
            speak("Scheduled shutdown cancelled.")
        else:
            speak("There is no scheduled shutdown to cancel.")
        return

    if command in ("confirm close tab", "yes close tab", "confirm closing tab"):
        with action_lock:
            if pending_action != "close_tab":
                speak("Please say close tab first.")
                return
            pending_action = None
        speak("Closing the active tab.")
        # This keyboard shortcut affects whichever window is currently active.
        pyautogui.hotkey("ctrl", "w")
        return

    if command in ("close youtube", "close google", "close website", "close browser", "close this page", "close current tab"):
        close_browser_tab()
        return

    if "close tab" in command or "close the tab" in command:
        close_browser_tab()
        return

    if command in ("confirm shutdown", "yes shutdown", "confirm laptop shutdown"):
        with action_lock:
            if pending_action != "shutdown":
                speak("Please say shutdown first.")
                return
            pending_action = None
        speak("Laptop shutdown is scheduled in 60 seconds. Say cancel shutdown if needed.")
        subprocess.Popen(["shutdown", "/s", "/t", str(SHUTDOWN_DELAY)], shell=False)
        return

    if ("shutdown" in command or "shut down" in command
            or "turn off laptop" in command or "switch off laptop" in command):
        with action_lock:
            pending_action = "shutdown"
        speak("This will shut down your laptop. Say confirm shutdown to proceed, or say cancel.")
        return

    if "time" in command:
        speak("The current time is " + datetime.now().strftime("%I:%M %p"))
        return

    if "date" in command:
        speak("Today's date is " + datetime.now().strftime("%d %B %Y"))
        return

    if any(x in command for x in ("read page", "read webpage", "read this page",
                                   "read website", "read the page")):
        threading.Thread(target=read_webpage, daemon=True).start()
        return

    youtube_prefixes = (
        "search youtube for ", "search on youtube for ",
        "youtube search ", "play on youtube ", "play "
    )
    for prefix in youtube_prefixes:
        if command.startswith(prefix):
            query = command[len(prefix):].strip()
            if not query:
                speak("Please tell me what to search for.")
                return
            last_url = "https://www.youtube.com/results?search_query=" + quote_plus(query)
            webbrowser.open(last_url)
            speak(f"Searching YouTube for {query}.")
            return

    google_prefixes = (
        "search google for ", "search on google for ",
        "google search ", "search for "
    )
    for prefix in google_prefixes:
        if command.startswith(prefix):
            query = command[len(prefix):].strip()
            if not query:
                speak("Please tell me what to search for.")
                return
            last_url = "https://www.google.com/search?q=" + quote_plus(query)
            webbrowser.open(last_url)
            speak(f"Searching Google for {query}.")
            return

    sites = {
        "google": "https://www.google.com",
        "youtube": "https://www.youtube.com",
        "gmail": "https://mail.google.com",
        "github": "https://github.com",
        "wikipedia": "https://www.wikipedia.org",
        "linkedin": "https://www.linkedin.com"
    }
    for site, url in sites.items():
        if command in (f"open {site}", f"open {site}.com", f"go to {site}",
                       f"launch {site}", f"start {site}") or command.startswith(f"open {site} "):
            last_url = url
            webbrowser.open_new_tab(url)
            speak(f"Opening {site} in your browser.")
            return

    if command in ("hello", "hi", "hey", "hello nishauri", "hi nishauri", "hey nishauri"):
        speak("Hello! I am here. What would you like help with?")
        return

    if "what can you do" in command or "how can you help" in command:
        process_command("help")
        return

    if command in ("exit", "quit", "stop assistant", "close assistant"):
        global continuous_listening
        continuous_listening = False
        speak("Goodbye! Until next time.")
        root.after(1800, root.destroy)
        return

    # Treat unrecognized speech as a natural-language question/request instead of
    # immediately saying the command is unknown.
    threading.Thread(target=answer_general_question, args=(command,), daemon=True).start()


# ------------------ Text command input ------------------

def send_text_command(event=None):
    command = command_entry.get().strip()
    if not command:
        return
    command_entry.delete(0, tk.END)
    log_message("You", command)
    threading.Thread(target=process_command, args=(command,), daemon=True).start()


# ------------------ Main GUI ------------------

root = tk.Tk()
root.title("Nishauri AI Assistant")
root.geometry("920x850")
root.minsize(720, 700)
root.configure(bg="#090E1F")

top = tk.Frame(root, bg="#090E1F")
top.pack(fill=tk.X, pady=(15, 2))

title_label = tk.Label(top, text="NISHAURI", font=("Segoe UI", 25, "bold"),
                       fg="#A6B8FF", bg="#090E1F")
title_label.pack()

subtitle = tk.Label(top, text="VOICE-POWERED DESKTOP ASSISTANT  •  ASK, SEARCH, CONTROL",
                    font=("Segoe UI", 9, "bold"), fg="#7F91C9", bg="#090E1F")
subtitle.pack(pady=(2, 0))

canvas = tk.Canvas(root, height=290, bg="#090E1F", highlightthickness=0)
canvas.pack(fill=tk.X, padx=10, pady=(0, 0))

status_label = tk.Label(root, text="READY  •  Click Start continuous listening or type below",
                        font=("Segoe UI", 10, "bold"), fg="#A6B8FF", bg="#090E1F")
status_label.pack(pady=(0, 8))

chat_box = scrolledtext.ScrolledText(
    root, wrap=tk.WORD, height=9, font=("Segoe UI", 10),
    bg="#121B31", fg="#EAF0FF", insertbackground="white",
    relief="flat", padx=12, pady=10
)
chat_box.pack(fill=tk.BOTH, expand=True, padx=18, pady=(2, 10))
chat_box.configure(state="disabled")

command_entry = tk.Entry(
    root, font=("Segoe UI", 12), bg="#1A2742", fg="white",
    insertbackground="white", relief="flat"
)
command_entry.pack(fill=tk.X, padx=18, pady=(0, 9), ipady=11)
command_entry.insert(0, "Type a command… e.g. search YouTube for Python")
command_entry.bind("<FocusIn>", lambda event: (
    command_entry.delete(0, tk.END)
    if command_entry.get().startswith("Type a command") else None
))
command_entry.bind("<Return>", send_text_command)

buttons = tk.Frame(root, bg="#090E1F")
buttons.pack(pady=(0, 15))

mic_button = tk.Button(
    buttons, text="🎙  Speak to Nishauri", command=start_listening,
    font=("Segoe UI", 10, "bold"), bg="#5865F2", fg="white",
    activebackground="#737EFF", activeforeground="white",
    relief="flat", padx=18, pady=11, cursor="hand2"
)
mic_button.grid(row=0, column=0, padx=5)

send_button = tk.Button(
    buttons, text="Send ✦", command=send_text_command,
    font=("Segoe UI", 10, "bold"), bg="#197C9D", fg="white",
    activebackground="#2497BA", activeforeground="white",
    relief="flat", padx=18, pady=11, cursor="hand2"
)
send_button.grid(row=0, column=1, padx=5)

help_button = tk.Button(
    buttons, text="Commands", command=lambda: process_command("help"),
    font=("Segoe UI", 10, "bold"), bg="#202D4B", fg="#DCE5FF",
    activebackground="#31436B", activeforeground="white",
    relief="flat", padx=18, pady=11, cursor="hand2"
)
help_button.grid(row=0, column=2, padx=5)

log_message("Nishauri", "Hello! I’m Nishauri. I can open websites, search the web, answer some general questions aloud, tell the time/date, and read webpage text. Try asking a question naturally or say ‘help’ for examples.")
draw_orb()
root.mainloop()
