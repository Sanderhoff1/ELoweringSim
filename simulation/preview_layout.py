"""Preview the Energy Flow canvas at the normal application size."""
from pathlib import Path
from .preview_energy import main as energy_preview


def main():
    energy_preview()
    Path('layout-preview.png').write_bytes(Path('energy-preview.png').read_bytes())
    print('Saved layout-preview.png (actual canvas geometry; sidebar space reserved)')


if __name__=='__main__':main()
