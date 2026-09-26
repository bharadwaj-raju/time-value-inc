from core_game import CoreGameState
from interstitials import LevelDoneState, WantResetState
from intro_screed import IntroScreed
from resources import res
from state import State


def get_next_stage(stage: str) -> str:
    if stage == "title-screen":
        return "intro-screed"
    elif stage == "intro-screed":
        return "tutorial-0"
    elif stage.startswith("tutorial-"):
        ntut = int(stage.removeprefix("tutorial-"))
        if ntut >= len(res.tutorials) - 1:
            return "level-0"
        return "tutorial-" + str(ntut + 1)
    elif stage.startswith("level-"):
        nlvl = int(stage.removeprefix("level-"))
        if nlvl >= len(res.levels) - 1:
            return "finished"
        return "level-" + str(nlvl + 1)
    elif stage == "finished" or stage == "want-reset":
        return "want-reset"
    print(f"don't know how to continue from {stage!r}")
    return "title-screen"


class LevelManager(State):
    def __init__(self, mgr):
        super().__init__(mgr)
        self.stage = res.save.last_stage
        print(f"Last stage per save: {self.stage}")
        print(self.mgr.stack)
        
    def start_stage(self, stage: str):
        if stage == "title-screen":
            self.mgr.pop()
        elif stage == "intro-screed":
            self.mgr.push(IntroScreed(self.mgr))
        elif stage.startswith("tutorial-"):
            ntut = int(stage.removeprefix("tutorial-"))
            self.mgr.push(CoreGameState(self.mgr, res.tutorials[ntut]))
        elif stage.startswith("level-"):
            nlvl = int(stage.removeprefix("level-"))
            self.mgr.push(CoreGameState(self.mgr, res.levels[nlvl]))
        elif stage == "finished":
            self.mgr.push(LevelDoneState(self.mgr, extra_message="That’s it! We accomplished our mission!"))
        elif stage == "want-reset":
            self.mgr.push(WantResetState(self.mgr))

    def update(self, dt):
        print(dt)
        if self.mgr.stack[-1] is not self:
            return
        old_saved = res.save.last_stage
        res.save.last_stage = self.stage
        res.save.save()
        print("Saved", self.stage)
        if old_saved != self.stage and (self.stage.startswith("tutorial-") or (self.stage.startswith("level-") and int(self.stage.removeprefix("level-")) != len(res.levels) - 1)):
            self.mgr.push(LevelDoneState(self.mgr, extra_message="There’s more, though…"))
            return
        self.stage = get_next_stage(self.stage)
        print(f"Next stage: {self.stage}")
        if self.stage == "title-screen":
            self.mgr.pop()
        else:
            self.start_stage(self.stage)
