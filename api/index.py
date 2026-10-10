import os
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent / 'King_Barber'
sys.path.insert(0, str(project_root))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'King_Barber.settings')

from King_Barber.wsgi import application