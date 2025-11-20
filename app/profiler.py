import time

class StepProfiler:
    def __init__(self):
        self.steps = []
        self._last = None

    def start(self):
        self._last = time.perf_counter()

    def step(self, name: str):
        if self._last is None:
            self._last = time.perf_counter()
        now = time.perf_counter()
        self.steps.append({"step": name, "duration_sec": round(now - self._last, 4)})
        self._last = now

    def result(self):
        total = sum(s["duration_sec"] for s in self.steps)
        return {"steps": self.steps, "total_sec": round(total, 4)}
