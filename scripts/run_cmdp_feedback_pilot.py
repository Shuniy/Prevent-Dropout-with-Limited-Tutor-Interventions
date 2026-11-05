"""Run the 12-student, four-month Step 5 development pilot."""
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.school.feedback_experiments import main

if __name__ == "__main__":
    main(pilot=True)
