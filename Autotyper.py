import pyautogui
import keyboard
import threading
import time
import random
import customtkinter as ctk
from tkinter import messagebox
import string

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

class AutoTyperApp:
    def __init__(self, root):
        self.root = root
        self.root.title("AutoTyper-Pro")
        self.root.geometry("600x450")
        self.root.wm_attributes("-topmost", 1)

        self.typing_thread = None
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.is_typing = False
        self.is_paused = False
        self.current_index = 0
        self.last_char_was_space = True
        self.bias_percent = 50
        self.error_percent = 1

        self.create_widgets()
        self.register_hotkeys()

    def create_widgets(self):
        self.duration_label = None
        ctk.CTkLabel(self.root, text="Input Text:").pack(pady=5)
        self.text_box = ctk.CTkTextbox(self.root, height=100, width=500)
        self.text_box.pack(pady=5)
        self.text_box.insert("1.0", "This is a text")

        frame = ctk.CTkFrame(self.root)
        frame.pack(pady=10)

        ctk.CTkLabel(frame, text="Minimum time interval (s)").grid(row=0, column=0, padx=5)
        self.min_delay = ctk.CTkEntry(frame, width=60)
        self.min_delay.grid(row=0, column=1, padx=5)
        self.min_delay.insert(0, "0.03")

        ctk.CTkLabel(frame, text="Maximum time interval (s)").grid(row=0, column=2, padx=5)
        self.max_delay = ctk.CTkEntry(frame, width=60)
        self.max_delay.grid(row=0, column=3, padx=5)
        self.max_delay.insert(0, "2")

        ctk.CTkLabel(frame, text="Speed deviation %:").grid(row=1, column=0, padx=5, pady=5)
        self.bias_slider = ctk.CTkSlider(frame, from_=0, to=100, number_of_steps=100, width=200)
        self.bias_slider.set(10)
        self.bias_slider.grid(row=1, column=1, columnspan=3, padx=5, sticky="w")

        ctk.CTkLabel(frame, text="Error rate %:").grid(row=2, column=0, padx=5, pady=5)
        self.error_slider = ctk.CTkSlider(frame, from_=0, to=100, number_of_steps=100, width=200)
        self.error_slider.set(6)
        self.error_slider.grid(row=2, column=1, columnspan=3, padx=5, sticky="w")

        self.estimate_button = ctk.CTkButton(self.root, text="Estimate Duration", command=self.estimate_duration)
        self.estimate_button.pack(pady=5)
        self.duration_label = ctk.CTkLabel(self.root, text="Estimated duration: Unknown", text_color="gray")
        self.duration_label.pack(pady=5)
        self.status_label = ctk.CTkLabel(self.root, text="Status: Waiting", text_color="blue")
        self.status_label.pack(pady=5)

        ctk.CTkLabel(self.root, text="F8 Start/Stop | F9 Pause/Resume", text_color="gray").pack()

    def estimate_duration(self):
        if self.is_typing or self.is_paused:
            self.duration_label.configure(text="Estimated duration: Only available when stopped", text_color="orange")
            return
        if not self.load_settings():
            self.duration_label.configure(text="Estimated duration: Invalid settings", text_color="red")
            return

        text = self.text_box.get("1.0", "end").strip()
        if not text:
            self.duration_label.configure(text="Estimated duration: No text", text_color="gray")
            return

        min_d = self.min_d
        max_d = self.max_d

        bias = self.bias_slider.get() / 100
        weight = 5
        power = (1 - 2 * bias) * weight + 1

        if power >= 0:
            word_ratio = 1 / (power + 1)
        else:
            word_ratio = 1 - 1 / (abs(power) + 1)

        avg_word_delay = min_d + (max_d - min_d) * 0.4 * word_ratio
        avg_symbol_delay = min_d + (max_d - min_d) * 0.7 * (1 - word_ratio)

        total = 0
        same_count = 1
        prev_char = ''
        for c in text:
            if c == prev_char:
                same_count += 1
            else:
                same_count = 1
            delay_factor = 0.5 if same_count >= 4 else 1.0
            if c.isalpha():
                total += avg_word_delay * delay_factor
            else:
                total += avg_symbol_delay * delay_factor
            if c in ".,!?，。！？；;":
                total += 0.3
            prev_char = c

        self.duration_label.configure(text=f"Estimated duration: ~{total:.2f} seconds", text_color="gray")

    def register_hotkeys(self):
        keyboard.add_hotkey('f8', self.toggle_typing, suppress=True)
        keyboard.add_hotkey('f9', self.toggle_pause, suppress=True)

    def toggle_typing(self):
        if self.is_typing:
            self.stop_event.set()
            self.pause_event.clear()
            self.status_label.configure(text="Status: Stopping...", text_color="red")
            if self.typing_thread and self.typing_thread.is_alive():
                self.typing_thread.join()
            self.finish_typing(stopped=True)
        else:
            if not self.load_settings():
                return
            self.text = self.text_box.get("1.0", "end").strip()
            if not self.text:
                messagebox.showwarning("Warning", "Please enter text.")
                return
            self.stop_event.clear()
            self.pause_event.clear()
            self.current_index = 0
            self.last_char_was_space = True
            self.is_typing = True
            self.lock_controls()
            self.status_label.configure(text="Status: Typing...", text_color="green")
            self.typing_thread = threading.Thread(target=self.type_text)
            self.typing_thread.start()

    def toggle_pause(self):
        if not self.is_typing:
            return
        if self.is_paused:
            if not self.load_settings():
                return
            self.pause_event.clear()
            self.lock_controls()
            self.status_label.configure(text="Status: Resumed", text_color="green")
        else:
            self.pause_event.set()
            self.unlock_controls()
            self.text_box.configure(state="disabled")
            self.status_label.configure(text="Status: Paused", text_color="orange")
        self.is_paused = not self.is_paused

    def load_settings(self):
        try:
            self.min_d = float(self.min_delay.get())
            self.max_d = float(self.max_delay.get())
            if self.min_d > self.max_d:
                self.min_d, self.max_d = self.max_d, self.min_d
            return True
        except ValueError:
            messagebox.showerror("Error", "Please enter valid delay values.")
            return False

    def refresh_runtime_settings(self):
        self.bias_percent = int(self.bias_slider.get())
        self.error_percent = int(self.error_slider.get())

    def count_same_previous_chars(self):
        if self.current_index == 0:
            return 0
        count = 1
        current_char = self.text[self.current_index - 1]
        i = self.current_index - 2
        while i >= 0 and self.text[i] == current_char:
            count += 1
            i -= 1
        return count

    def biased_delay(self):
        next_char = self.text[self.current_index] if self.current_index < len(self.text) else ' '
        is_letter = next_char.isalpha()
        base_min = self.min_d
        base_max = self.max_d
        if is_letter:
            sub_min = base_min
            sub_max = base_min + (base_max - base_min) * 0.4
        else:
            sub_min = base_min + (base_max - base_min) * 0.3
            sub_max = base_max
        if self.bias_percent == 0:
            return sub_min
        elif self.bias_percent == 100:
            return sub_max
        bias = self.bias_percent / 100
        weight = 5
        rand = random.random()
        power = (1 - 2 * bias) * weight + 1
        weighted_rand = rand ** power if power >= 0 else 1 - (1 - rand) ** abs(power)
        return sub_min + (sub_max - sub_min) * weighted_rand

    def type_text(self):
        fatigue_counter = 0
        while self.current_index < len(self.text):
            if self.stop_event.is_set():
                break
            if self.pause_event.is_set():
                self.refresh_runtime_settings()
                time.sleep(0.2)
                continue
            self.refresh_runtime_settings()
            fatigue_counter += 1
            char = self.text[self.current_index]
            delay = self.biased_delay()
            if self.last_char_was_space and char.isalpha():
                delay += random.uniform(0.02, 0.1)
            if random.random() < (self.error_percent / 100.0):
                if random.random() < 0.2:
                    while self.current_index > 0 and self.text[self.current_index - 1].isalnum():
                        pyautogui.press('backspace')
                        self.current_index -= 1
                        time.sleep(random.uniform(0.05, 0.12))
                    word = ''
                    while self.current_index < len(self.text) and self.text[self.current_index].isalnum():
                        word += self.text[self.current_index]
                        self.current_index += 1
                    for ch in word:
                        pyautogui.write(ch)
                        time.sleep(random.uniform(0.05, 0.15))
                    continue
                else:
                    pyautogui.write(random.choice(string.ascii_lowercase))
                    pyautogui.press('backspace')
            pyautogui.write(char)
            self.current_index += 1
            if char in ".,!?，。！？；;":
                delay += 0.3
            if self.count_same_previous_chars() >= 3:
                delay *= 0.5
            if fatigue_counter >= 30 and random.random() < (self.error_percent / 100.0):
                time.sleep(random.uniform(0.5, 2.0))
                fatigue_counter = 0
            time.sleep(delay)
            self.last_char_was_space = char.isspace()
        self.finish_typing(stopped=self.stop_event.is_set())

    def finish_typing(self, stopped=False):
        self.is_typing = False
        self.is_paused = False
        self.typing_thread = None
        self.unlock_controls()
        if stopped:
            self.status_label.configure(text="Status: Stopped", text_color="red")
        else:
            self.status_label.configure(text="Status: Completed", text_color="blue")

    def lock_controls(self):
        self.text_box.configure(state="disabled")
        self.min_delay.configure(state="disabled")
        self.max_delay.configure(state="disabled")

    def unlock_controls(self):
        self.text_box.configure(state="normal")
        self.min_delay.configure(state="normal")
        self.max_delay.configure(state="normal")

if __name__ == "__main__":
    root = ctk.CTk()
    app = AutoTyperApp(root)
    root.mainloop()
