"""Run the 100-student, 12-month Step 5 development integration comparison."""
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.school.feedback_experiments import main

if __name__ == "__main__":
    main()
