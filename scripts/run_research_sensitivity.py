"""Run the Step 6 secondary stage."""
from pathlib import Path
import sys
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.evaluation.research_experiments import main
if __name__ == "__main__":
    main(default_stage="secondary")
