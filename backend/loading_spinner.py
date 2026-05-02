import time
import threading
import functools
from itertools import cycle


class LoadingAnimation:
    def __init__(self, message, speed=0.1):
        self.message = message
        self.speed = speed
        self.kill_thread = False
        self.thread = threading.Thread(target=self.spinner, daemon=True)

    def spinner(self):
        spinner = cycle(["-", "\\", "|", "/"])
        for item in spinner:
            print(f"\r{self.message}... {item}", end="")
            time.sleep(self.speed)
            if self.kill_thread:
                print()
                return

    def start(self):
        self.thread.start()

    def kill(self):
        self.kill_thread = True
        self.thread.join()
        print("loading done")


def with_loading(message):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            loader = LoadingAnimation(message)
            loader.start()
            try:
                return func(*args, **kwargs)
            finally:
                loader.kill()

        return wrapper

    return decorator
