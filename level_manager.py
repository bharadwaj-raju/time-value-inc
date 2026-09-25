from interstitials import LevelDoneState
from core_game import CoreGameState
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
    print(f"don't know how to continue from {stage!r}")
    return "title-screen"


class LevelManager(State):
    def __init__(self, mgr):
        super().__init__(mgr)
        self.stage = res.save.last_stage
        print(f"Last stage per save: {self.stage}")
        
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

    def update(self, dt):
        if self.mgr.stack[-1] is not self:
            return
        res.save.last_stage = self.stage
        res.save.save()
        print("Saved")
        if self.stage.startswith(("level-", "tutorial-")):
            self.mgr.push(LevelDoneState(self.mgr, extra_message="There’s more, though…"))
        self.stage = get_next_stage(self.stage)
        print(f"Next stage: {self.stage}")
        self.start_stage(self.stage)
