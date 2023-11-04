import mylogging
import logging

logger = logging.getLogger(__name__)
import os

if not os.path.exists("data"):
    os.makedirs("data")
os.environ.setdefault("NICEGUI_STORAGE_PATH", "data")
from nicegui import ui
from bale import page, logo, scheduler


if __name__ in {"__main__", "__mp_main__"}:
    page.build()
    s = scheduler.Scheduler()
    ui.timer(0.1, s.start, once=True)
    ui.run(title="bale", favicon=logo.favicon, dark=True, reload=False)
