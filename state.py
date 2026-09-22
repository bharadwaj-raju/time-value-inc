class State:
    def __init__(self, mgr: "StateManager"):
        self.mgr = mgr
    def handle_event(self, event): pass
    def update(self, dt): pass
    def draw(self, surface): pass

class StateManager:
    def __init__(self):
        self.stack = []

    def push(self, state):
        self.stack.append(state)

    def pop(self):
        if self.stack:
            return self.stack.pop()

    def change(self, state):
        self.stack.clear()
        self.push(state)

    def handle_event(self, event):
        if self.stack:
            self.stack[-1].handle_event(event)

    def update(self, dt):
        if self.stack:
            self.stack[-1].update(dt)

    def draw(self, surface):
        for state in self.stack:
            state.draw(surface)

class Timer:
    def __init__(self, duration, repeating=False, callback=None):
        self.duration = duration
        self.repeating = repeating
        self.callback = callback
        self.time_left = duration
        self.active = False

    def start(self):
        self.time_left = self.duration
        self.active = True

    def stop(self):
        self.active = False

    def update(self, dt):
        if not self.active:
            return

        self.time_left -= dt
        if self.time_left <= 0:
            if self.callback:
                self.callback()

            if self.repeating:
                self.time_left += self.duration
            else:
                self.active = False
