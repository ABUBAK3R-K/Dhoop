import pytest
import sys
import os

# Add worker directory to sys.path so worker modules can be imported directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
